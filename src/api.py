from __future__ import annotations

from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.core import audit
from src.core.config import load_safety_limits
from src.core.errors import (
    GENERIC_SERVER_DETAIL,
    log_error,
    new_error_id,
)
from src.core.logging_config import configure_logging, get_request_id, set_request_id
from src.core.crypto import SecretConfigError
from src.core.profiles import (
    JsonFileProfileStore,
    ProfileCreate,
    ProfilePublic,
    ProfileStore,
)
from src.core.reports import (
    JsonFileReportStore,
    Report,
    ReportCreate,
    ReportStore,
    coerce_report_binds,
)
from src.core.schema_store import (
    JsonFileSchemaStore,
    SchemaRecord,
    SchemaStore,
    SchemaSummary,
)
from src.core.introspection import introspect_schema
from src.core.sql_safety import SqlSafetyError, assert_safe_select
from src.core.templates import Template, get_template, list_templates
from src.schema import schema_from_dict, schema_to_dict
from src.db import OracleClient, OracleConnectionConfig
from src.nl2sql import LLMConfig, generate_sql_from_nl
from src.schema import (
    Schema,
    attach_relationships,
    parse_relationships_dataframe,
    parse_schema_dataframe,
)

# Load .env for local/bare-metal runs. In Docker/Render real env vars are set
# directly, so this is a harmless no-op there. No secrets live in source.
load_dotenv()

# Structured logging to stdout (JSON by default; LOG_LEVEL/LOG_FORMAT via env).
configure_logging()

app = FastAPI(title="Ask Oracle Reports API", version="2.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------------------------------- #
# Observability: per-request correlation id (= client error_id) + error envelope
# --------------------------------------------------------------------------- #
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Assign/honour a correlation id, bind it for logging, echo it back.

    The same id is stamped on every log record (via the ``request_id``
    contextvar) and injected as ``error_id`` into every error body by the
    exception handlers below — so a client-visible failure maps to one exact
    server log line.
    """
    rid = request.headers.get("X-Request-ID") or new_error_id()
    set_request_id(rid)
    try:
        response = await call_next(request)
    finally:
        # Keep the id available to exception handlers running in this context.
        set_request_id(rid)
    response.headers["X-Request-ID"] = rid
    return response


def _db_error(exc: Exception, context: str) -> HTTPException:
    """Sanitize a raw driver/connection error: log it server-side (full detail,
    keyed by the request's error_id) and return a generic 400. The error body's
    ``error_id`` is attached by the HTTPException handler."""
    error_id = get_request_id() or new_error_id()
    log_error(exc, context=context, error_id=error_id, event="db_error")
    return HTTPException(status_code=400, detail="Database error — see server logs.")


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Preserve the existing ``detail`` (safe messages stay verbatim) and add
    ``error_id`` — additive, no contract break."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_id": get_request_id()},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """422 body keeps FastAPI's ``detail`` list and gains ``error_id``."""
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors()), "error_id": get_request_id()},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: never leak an internal error; log it server-side, return a
    generic 500 + ``error_id``."""
    error_id = get_request_id() or new_error_id()
    log_error(exc, context="unhandled", error_id=error_id, event="unhandled_error")
    return JSONResponse(
        status_code=500,
        content={"detail": GENERIC_SERVER_DETAIL, "error_id": error_id},
    )

# Pluggable storage backends. Swap for Sqlite*Store later without touching the
# routes below.
_store: ProfileStore = JsonFileProfileStore()
_report_store: ReportStore = JsonFileReportStore()
_schema_store: SchemaStore = JsonFileSchemaStore()


# --------------------------------------------------------------------------- #
# Request/response models
# --------------------------------------------------------------------------- #
class ConnectionConfig(BaseModel):
    host: str
    port: int = 1521
    service_name: Optional[str] = None
    sid: Optional[str] = None
    username: str
    password: str

    @model_validator(mode="after")
    def _require_service_or_sid(self) -> "ConnectionConfig":
        if not (self.service_name or self.sid):
            raise ValueError("Either service_name or sid must be provided.")
        return self


class LLMSettings(BaseModel):
    """Optional per-user/per-request LLM override. Omitted fields fall back to
    the server's environment configuration. The api_key is used transiently and
    is never logged or persisted."""

    provider: Optional[str] = Field(None, description='"groq" or "openai"')
    model: Optional[str] = None
    api_key: Optional[str] = Field(None, repr=False)  # never echoed in repr/logs (F6)
    base_url: Optional[str] = None


class NL2SQLRequest(BaseModel):
    natural_language: str = Field(..., description="User phrasing to convert to SQL")
    schema_csv: Optional[str] = Field(None, description="Schema CSV content as string")
    relationships_csv: Optional[str] = Field(None, description="Relationships CSV content as string")
    model: Optional[str] = None
    llm: Optional[LLMSettings] = Field(None, description="Per-user LLM provider/model/key override")


class SQLExecuteRequest(BaseModel):
    """Execute a query against either a stored profile OR an inline connection."""

    sql: str
    profile_id: Optional[str] = None
    connection: Optional[ConnectionConfig] = None
    max_rows: Optional[int] = None
    binds: Optional[Dict[str, Any]] = None  # Phase 4: bound as values, never interpolated

    @model_validator(mode="after")
    def _require_target(self) -> "SQLExecuteRequest":
        if not self.profile_id and self.connection is None:
            raise ValueError("Provide either profile_id or an inline connection.")
        if self.profile_id and self.connection is not None:
            raise ValueError("Provide exactly one of profile_id or connection, not both.")
        return self


class RunReportRequest(BaseModel):
    """Run a saved report. The connection target may come from the request
    (``profile_id``/``connection``) or fall back to the report's bound profile.
    ``binds`` are *raw* values keyed by parameter name; they are coerced via the
    report's declared parameters before reaching the chokepoint."""

    profile_id: Optional[str] = None
    connection: Optional[ConnectionConfig] = None
    binds: Optional[Dict[str, Any]] = None
    max_rows: Optional[int] = None


class SchemaCreate(BaseModel):
    """Save a schema snapshot from a serialized definition OR uploaded CSV text."""

    name: str = Field(..., min_length=1, max_length=120)
    definition: Optional[Dict[str, Any]] = None
    schema_csv: Optional[str] = None
    relationships_csv: Optional[str] = None

    @model_validator(mode="after")
    def _require_source(self) -> "SchemaCreate":
        if self.definition is None and not self.schema_csv:
            raise ValueError("Provide either 'definition' or 'schema_csv'.")
        return self


class IntrospectRequest(BaseModel):
    """Introspect a schema from the data-dictionary via the SELECT-only chokepoint."""

    profile_id: Optional[str] = None
    connection: Optional[ConnectionConfig] = None
    # No min_length: a blank/whitespace owner is normalized to a uniform 400 by
    # the orchestrator (review F-5), rather than 422 for "" vs 400 for "   ".
    owner: str
    table_like: str = "%"
    save: bool = False
    name: Optional[str] = None

    @model_validator(mode="after")
    def _require_target(self) -> "IntrospectRequest":
        if not self.profile_id and self.connection is None:
            raise ValueError("Provide either profile_id or connection.")
        if self.profile_id and self.connection is not None:
            raise ValueError("Provide exactly one of profile_id or connection, not both.")
        return self


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #
@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


# --------------------------------------------------------------------------- #
# Connection profiles
# --------------------------------------------------------------------------- #
@app.post("/profiles", response_model=ProfilePublic, status_code=201)
def create_profile(body: ProfileCreate) -> ProfilePublic:
    try:
        profile = _store.create(body)
    except ValueError as exc:
        # Duplicate name or missing service/sid.
        raise HTTPException(status_code=409, detail=str(exc))
    except SecretConfigError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    audit.audit_profile_usage(profile.id, profile.username, "create")
    return profile


@app.get("/profiles", response_model=List[ProfilePublic])
def list_profiles() -> List[ProfilePublic]:
    return _store.list()


@app.get("/profiles/{profile_id}", response_model=ProfilePublic)
def get_profile(profile_id: str) -> ProfilePublic:
    profile = _store.get(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return profile


@app.delete("/profiles/{profile_id}", status_code=204)
def delete_profile(profile_id: str) -> Response:
    if not _store.delete(profile_id):
        raise HTTPException(status_code=404, detail="Profile not found.")
    audit.audit_profile_usage(profile_id, None, "delete")
    return Response(status_code=204)


@app.post("/profiles/{profile_id}/test")
def test_profile(profile_id: str) -> Dict[str, Any]:
    resolved = _store.resolve(profile_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Profile not found.")
    client = OracleClient(
        OracleConnectionConfig(
            host=resolved.host,
            port=resolved.port,
            service_name=resolved.service_name,
            sid=resolved.sid,
            username=resolved.username,
            password=resolved.password,
        )
    )
    try:
        result = client.run_select("SELECT 1 FROM DUAL")
    except Exception as exc:  # noqa: BLE001 - DB/connection errors (sanitized, ITM-015)
        raise _db_error(exc, "profile-test")
    audit.audit_profile_usage(profile_id, resolved.username, "test")
    return {"ok": True, "elapsed_seconds": result.elapsed_seconds}


@app.post("/test-connection")
def test_connection(conn: ConnectionConfig) -> Dict[str, Any]:
    """Test an inline (unsaved) connection without persisting it."""
    client = OracleClient(
        OracleConnectionConfig(
            host=conn.host,
            port=conn.port,
            service_name=conn.service_name,
            sid=conn.sid,
            username=conn.username,
            password=conn.password,
        )
    )
    try:
        result = client.run_select("SELECT 1 FROM DUAL")
    except Exception as exc:  # noqa: BLE001 - DB/connection errors (sanitized, ITM-015)
        raise _db_error(exc, "test-connection")
    return {"ok": True, "elapsed_seconds": result.elapsed_seconds, "columns": result.columns, "rows": result.rows}


# --------------------------------------------------------------------------- #
# NL -> SQL (proposes SQL only; never executes)
# --------------------------------------------------------------------------- #
@app.post("/nl2sql")
def nl2sql(req: NL2SQLRequest) -> Dict[str, Any]:
    try:
        schema = Schema()
        if req.schema_csv:
            import pandas as pd
            from io import StringIO

            schema = parse_schema_dataframe(pd.read_csv(StringIO(req.schema_csv)))
        if req.relationships_csv:
            import pandas as pd
            from io import StringIO

            rels = parse_relationships_dataframe(pd.read_csv(StringIO(req.relationships_csv)))
            schema = attach_relationships(schema, rels)

        llm_cfg = LLMConfig(**req.llm.model_dump()) if req.llm else None
        result = generate_sql_from_nl(req.natural_language, schema, model=req.model, llm=llm_cfg)
        confidence = (
            {"level": result.confidence.level, "reasons": result.confidence.reasons}
            if result.confidence
            else None
        )
        return {"sql": result.sql, "explanation": result.explanation, "confidence": confidence}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))


# --------------------------------------------------------------------------- #
# Execute (the single safe chokepoint for running SQL)
# --------------------------------------------------------------------------- #
def _resolve_target(
    profile_id: Optional[str], connection: Optional[ConnectionConfig]
) -> "tuple[OracleConnectionConfig, str, Optional[str]]":
    """Resolve a (conn_cfg, username, profile_id) target from a stored profile
    or an inline connection. Raises 404 for an unknown profile."""
    if profile_id:
        resolved = _store.resolve(profile_id)
        if resolved is None:
            raise HTTPException(status_code=404, detail="Profile not found.")
        return (
            OracleConnectionConfig(
                host=resolved.host,
                port=resolved.port,
                service_name=resolved.service_name,
                sid=resolved.sid,
                username=resolved.username,
                password=resolved.password,
            ),
            resolved.username,
            profile_id,
        )
    c = connection  # guaranteed present by the caller
    return (
        OracleConnectionConfig(
            host=c.host,
            port=c.port,
            service_name=c.service_name,
            sid=c.sid,
            username=c.username,
            password=c.password,
        ),
        c.username,
        None,
    )


def _run_sql(
    *,
    sql: str,
    conn_cfg: "OracleConnectionConfig",
    username: str,
    profile_id: Optional[str],
    binds: Optional[Dict[str, Any]],
    max_rows: Optional[int],
) -> Dict[str, Any]:
    """The shared chokepoint body used by /execute and /reports/{id}/run."""
    # Safety gate: reject anything that is not a provably read-only SELECT/CTE.
    safety = assert_safe_select(sql)
    if not safety.allowed:
        audit.audit_execution(
            source="api", sql=sql, allowed=False, profile_id=profile_id, username=username, reason=safety.reason
        )
        raise HTTPException(status_code=400, detail=safety.reason or "Query rejected by safety layer.")

    # Narrow (never widen) the global row cap if the caller requested fewer rows.
    limits = load_safety_limits()
    if max_rows is not None:
        limits = limits.model_copy(update={"max_rows": max(1, min(max_rows, limits.max_rows))})

    client = OracleClient(conn_cfg)
    try:
        result = client.run_select(sql, limits=limits, binds=binds)
    except SqlSafetyError as exc:
        audit.audit_execution(
            source="api", sql=sql, allowed=False, profile_id=profile_id, username=username, reason=str(exc)
        )
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - DB/connection errors (sanitized, ITM-015)
        audit.audit_execution(
            source="api", sql=sql, allowed=True, profile_id=profile_id, username=username, reason="execution_error"
        )
        raise _db_error(exc, "execute")

    audit.audit_execution(
        source="api",
        sql=sql,
        allowed=True,
        profile_id=profile_id,
        username=username,
        row_count=result.row_count,
        elapsed_seconds=result.elapsed_seconds,
        truncated=result.truncated,
    )
    return {
        "columns": result.columns,
        "rows": result.rows,
        "elapsed_seconds": result.elapsed_seconds,
        "row_count": result.row_count,
        "truncated": result.truncated,
    }


@app.post("/execute")
def execute(req: SQLExecuteRequest) -> Dict[str, Any]:
    conn_cfg, username, profile_id = _resolve_target(req.profile_id, req.connection)
    return _run_sql(
        sql=req.sql,
        conn_cfg=conn_cfg,
        username=username,
        profile_id=profile_id,
        binds=req.binds,
        max_rows=req.max_rows,
    )


# --------------------------------------------------------------------------- #
# Saved reports (CRUD + run); run goes through the same /execute chokepoint
# --------------------------------------------------------------------------- #
@app.post("/reports", response_model=Report, status_code=201)
def create_report(body: ReportCreate) -> Report:
    try:
        return _report_store.create(body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.get("/reports", response_model=List[Report])
def list_reports() -> List[Report]:
    return _report_store.list()


@app.get("/reports/{report_id}", response_model=Report)
def get_report(report_id: str) -> Report:
    report = _report_store.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return report


@app.put("/reports/{report_id}", response_model=Report)
def update_report(report_id: str, body: ReportCreate) -> Report:
    try:
        updated = _report_store.update(report_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if updated is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return updated


@app.delete("/reports/{report_id}", status_code=204)
def delete_report(report_id: str) -> Response:
    if not _report_store.delete(report_id):
        raise HTTPException(status_code=404, detail="Report not found.")
    return Response(status_code=204)


@app.post("/reports/{report_id}/run")
def run_report(report_id: str, req: RunReportRequest) -> Dict[str, Any]:
    report = _report_store.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")

    # Coerce raw values against the report's declared parameters (defaults,
    # required-enforcement, type coercion, unknown-key rejection).
    try:
        binds = coerce_report_binds(report.parameters, req.binds)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Connection target: request override wins, else the report's bound profile.
    effective_profile = req.profile_id or report.default_profile_id
    if effective_profile:
        conn_cfg, username, profile_id = _resolve_target(effective_profile, None)
    elif req.connection is not None:
        conn_cfg, username, profile_id = _resolve_target(None, req.connection)
    else:
        raise HTTPException(
            status_code=400,
            detail="No connection target: provide a profile_id/connection or bind the report to a profile.",
        )

    return _run_sql(
        sql=report.sql,
        conn_cfg=conn_cfg,
        username=username,
        profile_id=profile_id,
        binds=binds,
        max_rows=req.max_rows,
    )


# --------------------------------------------------------------------------- #
# Templates (read-only curated EBS starter catalog)
# --------------------------------------------------------------------------- #
@app.get("/templates", response_model=List[Template])
def get_templates() -> List[Template]:
    return list_templates()


@app.get("/templates/{template_id}", response_model=Template)
def get_template_by_id(template_id: str) -> Template:
    template = get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found.")
    return template


# --------------------------------------------------------------------------- #
# Saved schemas (data-dictionary snapshots) + live introspection
# --------------------------------------------------------------------------- #
@app.post("/schemas", response_model=SchemaRecord, status_code=201)
def create_schema(body: SchemaCreate) -> SchemaRecord:
    if body.definition is not None:
        # Normalize to enforce metadata-only persistence (review F-1): reading the
        # definition back through schema_from_dict drops any non-schema keys
        # (injected secrets, row data, connection strings) before it is stored.
        definition = schema_to_dict(schema_from_dict(body.definition))
    else:
        import pandas as pd
        from io import StringIO

        parsed = parse_schema_dataframe(pd.read_csv(StringIO(body.schema_csv)))
        if body.relationships_csv:
            rels = parse_relationships_dataframe(pd.read_csv(StringIO(body.relationships_csv)))
            parsed = attach_relationships(parsed, rels)
        definition = schema_to_dict(parsed)
    try:
        return _schema_store.create(body.name, definition, source="upload")
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@app.get("/schemas", response_model=List[SchemaSummary])
def list_schemas() -> List[SchemaSummary]:
    return _schema_store.list()


@app.get("/schemas/{schema_id}", response_model=SchemaRecord)
def get_schema(schema_id: str) -> SchemaRecord:
    record = _schema_store.get(schema_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Schema not found.")
    return record


@app.delete("/schemas/{schema_id}", status_code=204)
def delete_schema(schema_id: str) -> Response:
    if not _schema_store.delete(schema_id):
        raise HTTPException(status_code=404, detail="Schema not found.")
    return Response(status_code=204)


@app.post("/schemas/introspect")
def introspect(req: IntrospectRequest) -> Dict[str, Any]:
    conn_cfg, _username, profile_id = _resolve_target(req.profile_id, req.connection)
    client = OracleClient(conn_cfg)
    try:
        result = introspect_schema(client, owner=req.owner, table_like=req.table_like)
    except ValueError as exc:
        # Safe, intentional validation message (e.g. blank owner) — stays verbatim.
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - DB/connection errors (sanitized, ITM-015)
        raise _db_error(exc, "introspect")

    definition = schema_to_dict(result.schema)
    saved: Optional[Dict[str, Any]] = None
    if req.save:
        name = req.name or f"{req.owner.upper()} (introspected)"
        try:
            record = _schema_store.create(
                name, definition, source="introspection", profile_id=profile_id
            )
            saved = record.summary().model_dump()
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))

    return {
        "definition": definition,
        "table_count": len(definition.get("tables") or {}),
        "warnings": result.warnings,
        "truncated": result.truncated,
        "saved": saved,
    }


# Run: uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
