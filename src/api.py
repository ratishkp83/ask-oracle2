from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, get_args

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.core import audit, metrics
from src.core.auth import require_api_key
from src.core.config import load_safety_limits
from src.core.errors import (
    GENERIC_NL2SQL_DETAIL,
    GENERIC_SERVER_DETAIL,
    log_error,
    new_error_id,
    sanitize_correlation_id,
)
from src.core.llm.base import LLMError
from src.core.logging_config import configure_logging, get_request_id, set_request_id
from src.core.crypto import SecretConfigError
from src.core.profiles import (
    JsonFileProfileStore,
    ProfileCreate,
    ProfilePublic,
    ProfileStore,
    seed_profile_from_env,
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
from src.core.introspection import (
    capture_value_domains,
    introspect_schema,
    profile_schema,
)
from src.core.profiling import build_optimization_advisory, compute_readiness
from src.core.sql_safety import SqlSafetyError, assert_safe_select
from src.core.templates import Module, Template, get_template, list_templates
from src.core.ebs_packs import EbsPack, get_pack, list_packs
from src.core.mailer import email_enabled, send_html_bundle_email, send_report_email

_EBS_MODULES = set(get_args(Module))  # {"GL","AP","AR","PO","OM"}
from src.schema import schema_from_dict, schema_to_dict
from src.db import OracleClient, OracleConnectionConfig
from src.core.db_factory import make_client
from src.core.db_postgres import PostgresConnectionConfig
from src.core.introspection_postgres import introspect_schema_postgres
from src.nl2sql import LLMConfig, generate_sql_from_nl
from src.utils import dataframe_to_csv_bytes, dataframe_to_excel_bytes
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

# Opt-in API-key auth (ADR-013, ITM-009): enforced app-wide only when
# APP_API_KEY is set; /health stays exempt for liveness probes.
app = FastAPI(
    title="Ask Oracle Reports API",
    version="2.2.0",
    dependencies=[Depends(require_api_key)],
)


def _cors_config() -> "tuple[List[str], bool]":
    """Explicit origins from ``ALLOWED_ORIGINS`` (comma-separated; ADR-013).

    A literal ``"*"`` forfeits credentials, so the wildcard+credentials
    combination (the ITM-009 finding) is unrepresentable. A blank/whitespace
    value falls back to the localhost default rather than denying all origins
    (review r1/R3). Evaluated once at import — changing ``ALLOWED_ORIGINS``
    requires a process restart (unlike ``APP_API_KEY``, which is read
    per-request); documented in D7.
    """
    raw = (os.environ.get("ALLOWED_ORIGINS") or "").strip() or "http://localhost:8501,http://localhost:3000"
    origins = [o.strip() for o in raw.split(",") if o.strip()]
    return origins, "*" not in origins


_allowed_origins, _allow_credentials = _cors_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=_allow_credentials,
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
    # Sanitize any inbound id (attacker-controlled) before it reaches headers/logs (F-3).
    rid = sanitize_correlation_id(request.headers.get("X-Request-ID")) or new_error_id()
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
    ``error_id`` is attached by the HTTPException handler — and we bind the same
    id to the context so the logged id and the returned id cannot diverge even if
    the middleware was skipped (F-4)."""
    error_id = get_request_id() or new_error_id()
    set_request_id(error_id)
    log_error(exc, context=context, error_id=error_id, event="db_error")
    # User-facing: friendly + support-oriented (no operator phrasing). The full
    # driver detail is logged server-side and the error_id below is the bridge to
    # it for support (ITM-015 / readability feedback 2026-06-15).
    return HTTPException(
        status_code=400,
        detail="A database error occurred while running your request. Please try again, or contact IT support with this reference.",
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Preserve the existing ``detail`` (safe messages stay verbatim) and add
    ``error_id`` — additive, no contract break."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_id": get_request_id() or new_error_id()},
        headers=getattr(exc, "headers", None),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """422 body keeps FastAPI's ``detail`` list and gains ``error_id``."""
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors()), "error_id": get_request_id() or new_error_id()},
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
# Stateless/ephemeral deploys (e.g. Render's free tier, whose disk is wiped on
# every restart) restore their DB connection from SEED_* env vars on boot, so it
# survives sleeps and redeploys without a paid disk. No-op when unset; idempotent
# when a disk does persist. See docs/DEPLOY-render.md.
seed_profile_from_env(_store)
_report_store: ReportStore = JsonFileReportStore()
_schema_store: SchemaStore = JsonFileSchemaStore()


# --------------------------------------------------------------------------- #
# Request/response models
# --------------------------------------------------------------------------- #
class ConnectionConfig(BaseModel):
    engine: str = "oracle"  # "oracle" | "postgres"
    host: str
    port: int = 1521
    service_name: Optional[str] = None
    sid: Optional[str] = None
    database: Optional[str] = None
    sslmode: Optional[str] = None
    current_schema: Optional[str] = None
    username: str
    password: str

    @model_validator(mode="after")
    def _require_target(self) -> "ConnectionConfig":
        if self.engine == "postgres":
            if not self.database:
                raise ValueError("A database name is required for a PostgreSQL connection.")
        elif not (self.service_name or self.sid):
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
    schema_id: Optional[str] = Field(
        None,
        description=(
            "Id of a saved schema to use as NL→SQL context. Loaded server-side via "
            "schema_from_dict (table/column names only — no row data); ignored when "
            "schema_csv is supplied."
        ),
    )
    model: Optional[str] = None
    llm: Optional[LLMSettings] = Field(None, description="Per-user LLM provider/model/key override")
    ebs_modules: Optional[List[str]] = Field(
        None, description="Opt-in EBS module packs to add as curated metadata context (e.g. ['AP','GL'])"
    )
    # Target SQL dialect so generation matches where the SQL will run ("oracle" |
    # "postgres"). The client sends it from the selected connection's engine.
    dialect: Optional[str] = Field(None, description='"oracle" (default) or "postgres"')

    @field_validator("ebs_modules")
    @classmethod
    def _validate_ebs_modules(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        # Reject unknown modules (422) instead of silently ignoring them (review
        # P7-R1-F1); normalize case so ['ap'] works like ['AP'].
        if value is None:
            return value
        normalized, unknown = [], []
        for m in value:
            mu = (m or "").strip().upper()
            (normalized if mu in _EBS_MODULES else unknown).append(mu if mu in _EBS_MODULES else m)
        if unknown:
            raise ValueError(
                f"Unknown EBS module(s): {', '.join(unknown)}. Valid: {', '.join(sorted(_EBS_MODULES))}."
            )
        return normalized


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


class EmailReportRequest(BaseModel):
    """Email an already-fetched result as a CSV/Excel attachment (Phase 9, ADR-020).

    The client passes back the *exact result already shown* (``columns`` + ``rows``)
    — no re-query, no extra DB hit. **No LLM touches this path**; ``body`` is
    user-typed. The send reuses the Phase-8 mailer chokepoint unchanged (header-
    injection guard, allow-list, size cap, audit log). ``attachment_format`` is
    ``"csv"`` or ``"xlsx"``."""

    to: str
    subject: str
    body: str = ""
    attachment_format: str = "csv"
    columns: List[str]
    rows: List[List[Any]]
    cc: str = ""
    filename: Optional[str] = None

    @field_validator("columns")
    @classmethod
    def _require_columns(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("columns must be a non-empty list.")
        return value


class EmailBundleRequest(BaseModel):
    """Email a prebuilt cascading-report **HTML bundle** as an ``.html`` attachment
    (Phase 10, ADR-026).

    The client passes the already-assembled bundle (built locally from the result
    it already holds) — **no LLM, no re-query**. Reuses the Phase-8 mailer chokepoint
    unchanged (header-injection guard, allow-list, size cap, audit log)."""

    to: str
    subject: str
    body: str = ""
    html: str
    cc: str = ""
    filename: Optional[str] = None

    @field_validator("html")
    @classmethod
    def _require_html(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("html must be a non-empty cascading-report document.")
        return value


class ExportRequest(BaseModel):
    """Download an already-fetched result as a CSV/Excel file (Phase 9). Like the
    email path: no LLM, no re-query — the file is built from the shown result.
    Excel is generated server-side (openpyxl) so no spreadsheet library ships to
    the browser. ``format`` is ``"csv"`` or ``"xlsx"``."""

    columns: List[str]
    rows: List[List[Any]]
    format: str = "xlsx"
    filename: Optional[str] = None

    @field_validator("columns")
    @classmethod
    def _require_columns(cls, value: List[str]) -> List[str]:
        if not value:
            raise ValueError("columns must be a non-empty list.")
        return value


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


class ProfileRequest(IntrospectRequest):
    """Profile a schema (Phase 11): enriched Channel-A metadata + optional, opt-in
    Channel-B value-domain sampling, the Optimization Advisory, and the readiness gate.
    """

    # Update an existing saved schema in place (else create when save=True).
    schema_id: Optional[str] = None
    # Opt-in (default none): "TABLE.COLUMN" columns to sample value domains for.
    sample_value_columns: List[str] = Field(default_factory=list)
    # Engineer-supplied semantics to merge into the readiness computation/persistence.
    semantics: Optional[Dict[str, Any]] = None
    enforcement: str = "soft"  # soft | hard


# --------------------------------------------------------------------------- #
# Routes are defined on a router, then mounted **twice** — at the root (for
# back-compat) and under ``/v1`` (T-18). Exception handlers, middleware, and the
# app-level auth dependency stay on ``app`` and apply to both mounts.
# --------------------------------------------------------------------------- #
router = APIRouter()


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #
@router.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@router.get("/metrics")
def get_metrics() -> Dict[str, Any]:
    """Read-only in-process metrics: query counts + latency (no data/secrets).

    In-memory; resets on restart. Requires the API key when auth is enabled
    (ADR-013); only /health stays open for liveness probes.
    """
    return metrics.snapshot()


# --------------------------------------------------------------------------- #
# Connection profiles
# --------------------------------------------------------------------------- #
@router.post("/profiles", response_model=ProfilePublic, status_code=201)
def create_profile(body: ProfileCreate) -> ProfilePublic:
    try:
        profile = _store.create(body)
    except ValueError as exc:
        # Duplicate name or missing service/sid.
        raise HTTPException(status_code=409, detail=str(exc))
    except SecretConfigError as exc:
        # Intentional operator guidance (app-generated constants) — verbatim per
        # charter D-F, but now with a server-side breadcrumb keyed to the same
        # error_id the handler injects (ITM-017).
        error_id = get_request_id() or new_error_id()
        set_request_id(error_id)
        log_error(exc, context="profiles.secret_config", error_id=error_id)
        raise HTTPException(status_code=500, detail=str(exc))
    audit.audit_profile_usage(profile.id, profile.username, "create")
    return profile


@router.get("/profiles", response_model=List[ProfilePublic])
def list_profiles() -> List[ProfilePublic]:
    return _store.list()


@router.get("/profiles/{profile_id}", response_model=ProfilePublic)
def get_profile(profile_id: str) -> ProfilePublic:
    profile = _store.get(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found.")
    return profile


@router.delete("/profiles/{profile_id}", status_code=204)
def delete_profile(profile_id: str) -> Response:
    if not _store.delete(profile_id):
        raise HTTPException(status_code=404, detail="Profile not found.")
    audit.audit_profile_usage(profile_id, None, "delete")
    return Response(status_code=204)


@router.post("/profiles/{profile_id}/test")
def test_profile(profile_id: str) -> Dict[str, Any]:
    resolved = _store.resolve(profile_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="Profile not found.")
    cfg = _make_config(
        engine=resolved.engine, host=resolved.host, port=resolved.port,
        service_name=resolved.service_name, sid=resolved.sid,
        database=resolved.database, sslmode=resolved.sslmode,
        current_schema=resolved.current_schema, username=resolved.username,
        password=resolved.password,
    )
    client = make_client(cfg)
    probe = "SELECT 1" if _dialect_for(cfg) == "postgres" else "SELECT 1 FROM DUAL"
    try:
        result = client.run_select(probe)
    except Exception as exc:  # noqa: BLE001 - DB/connection errors (sanitized, ITM-015)
        raise _db_error(exc, "profile-test")
    audit.audit_profile_usage(profile_id, resolved.username, "test")
    return {"ok": True, "elapsed_seconds": result.elapsed_seconds}


@router.post("/test-connection")
def test_connection(conn: ConnectionConfig) -> Dict[str, Any]:
    """Test an inline (unsaved) connection without persisting it."""
    cfg = _make_config(
        engine=conn.engine, host=conn.host, port=conn.port,
        service_name=conn.service_name, sid=conn.sid, database=conn.database,
        sslmode=conn.sslmode, current_schema=conn.current_schema,
        username=conn.username, password=conn.password,
    )
    client = make_client(cfg)
    probe = "SELECT 1" if _dialect_for(cfg) == "postgres" else "SELECT 1 FROM DUAL"
    try:
        result = client.run_select(probe)
    except Exception as exc:  # noqa: BLE001 - DB/connection errors (sanitized, ITM-015)
        raise _db_error(exc, "test-connection")
    return {"ok": True, "elapsed_seconds": result.elapsed_seconds, "columns": result.columns, "rows": result.rows}


# --------------------------------------------------------------------------- #
# NL -> SQL (proposes SQL only; never executes)
# --------------------------------------------------------------------------- #
@router.post("/nl2sql")
def nl2sql(req: NL2SQLRequest) -> Dict[str, Any]:
    # Resolve a saved schema before the try so an unknown id returns a clean 404
    # (a sanitized 400 would otherwise swallow it). schema_csv, when present, wins.
    saved_definition: Optional[Dict[str, Any]] = None
    if req.schema_id and not req.schema_csv:
        record = _schema_store.get(req.schema_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Schema not found.")
        saved_definition = record.definition
    try:
        schema = Schema()
        if req.schema_csv:
            import pandas as pd
            from io import StringIO

            schema = parse_schema_dataframe(pd.read_csv(StringIO(req.schema_csv)))
        elif saved_definition is not None:
            # Names-only reconstruction (schema_from_dict drops anything that isn't
            # a known table/column/relationship field) — invariant 3 holds.
            schema = schema_from_dict(saved_definition)
        if req.relationships_csv:
            import pandas as pd
            from io import StringIO

            rels = parse_relationships_dataframe(pd.read_csv(StringIO(req.relationships_csv)))
            schema = attach_relationships(schema, rels)

        llm_cfg = LLMConfig(**req.llm.model_dump()) if req.llm else None
        result = generate_sql_from_nl(
            req.natural_language, schema, model=req.model, llm=llm_cfg,
            ebs_modules=req.ebs_modules, dialect=(req.dialect or "oracle"),
        )
        confidence = (
            {"level": result.confidence.level, "reasons": result.confidence.reasons}
            if result.confidence
            else None
        )
        return {
            "sql": result.sql,
            "explanation": result.explanation,
            "interpreted_question": result.interpreted_question,
            "confidence": confidence,
            "answerable": result.answerable,
            "message": result.message,
        }
    except (ValueError, LLMError) as exc:
        # Intentional/clean messages stay verbatim (the ADR-012 rule): our own
        # validation ValueErrors (empty schema / empty NL input, or a malformed
        # schema_csv from this same request) and LLMError, which nl2sql already maps
        # provider failures into (F2). Note: a non-SELECT/off-topic generation no
        # longer raises here — nl2sql returns answerable=False (ADR-025).
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 — unexpected: sanitize (ITM-017)
        error_id = get_request_id() or new_error_id()
        set_request_id(error_id)
        log_error(exc, context="nl2sql", error_id=error_id)
        raise HTTPException(status_code=400, detail=GENERIC_NL2SQL_DETAIL)


# --------------------------------------------------------------------------- #
# Execute (the single safe chokepoint for running SQL)
# --------------------------------------------------------------------------- #
def _make_config(
    *, engine, host, port, service_name, sid, database, sslmode, current_schema, username, password
):
    """Build the engine-specific connection config. Postgres uses database +
    search_path (the saved current_schema); Oracle uses service_name/sid + the
    ALTER SESSION default schema. Defaults to Oracle for back-compat."""
    if (engine or "oracle") == "postgres":
        return PostgresConnectionConfig(
            host=host,
            port=port,
            database=database or "postgres",
            username=username,
            password=password,
            sslmode=sslmode or "require",
            search_path=current_schema,
        )
    return OracleConnectionConfig(
        host=host,
        port=port,
        service_name=service_name,
        sid=sid,
        username=username,
        password=password,
        # Saved default schema so the AI's unqualified names resolve (ADR-018, BUG-008).
        current_schema=current_schema,
    )


def _resolve_target(profile_id: Optional[str], connection: Optional[ConnectionConfig]):
    """Resolve a (conn_cfg, username, profile_id) target — Oracle or Postgres —
    from a stored profile or an inline connection. Raises 404 for an unknown profile."""
    if profile_id:
        resolved = _store.resolve(profile_id)
        if resolved is None:
            raise HTTPException(status_code=404, detail="Profile not found.")
        cfg = _make_config(
            engine=resolved.engine, host=resolved.host, port=resolved.port,
            service_name=resolved.service_name, sid=resolved.sid,
            database=resolved.database, sslmode=resolved.sslmode,
            current_schema=resolved.current_schema, username=resolved.username,
            password=resolved.password,
        )
        return cfg, resolved.username, profile_id
    c = connection  # guaranteed present by the caller
    cfg = _make_config(
        engine=getattr(c, "engine", "oracle"), host=c.host, port=c.port,
        service_name=c.service_name, sid=c.sid, database=c.database,
        sslmode=c.sslmode, current_schema=c.current_schema,
        username=c.username, password=c.password,
    )
    return cfg, c.username, None


def _dialect_for(conn_cfg) -> str:
    return "postgres" if isinstance(conn_cfg, PostgresConnectionConfig) else "oracle"


def _run_sql(
    *,
    sql: str,
    conn_cfg,
    username: str,
    profile_id: Optional[str],
    binds: Optional[Dict[str, Any]],
    max_rows: Optional[int],
) -> Dict[str, Any]:
    """The shared chokepoint body used by /execute and /reports/{id}/run."""
    # Safety gate: reject anything that is not a provably read-only SELECT/CTE
    # (engine dialect so the same guarantee holds for Oracle and Postgres).
    safety = assert_safe_select(sql, dialect=_dialect_for(conn_cfg))
    if not safety.allowed:
        audit.audit_execution(
            source="api", sql=sql, allowed=False, profile_id=profile_id, username=username, reason=safety.reason
        )
        metrics.increment("queries_rejected")
        raise HTTPException(status_code=400, detail=safety.reason or "Query rejected by safety layer.")

    # Narrow (never widen) the global row cap if the caller requested fewer rows.
    limits = load_safety_limits()
    if max_rows is not None:
        limits = limits.model_copy(update={"max_rows": max(1, min(max_rows, limits.max_rows))})

    client = make_client(conn_cfg)
    try:
        result = client.run_select(sql, limits=limits, binds=binds)
    except SqlSafetyError as exc:
        audit.audit_execution(
            source="api", sql=sql, allowed=False, profile_id=profile_id, username=username, reason=str(exc)
        )
        metrics.increment("queries_rejected")
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - DB/connection errors (sanitized, ITM-015)
        audit.audit_execution(
            source="api", sql=sql, allowed=True, profile_id=profile_id, username=username, reason="execution_error"
        )
        metrics.increment("queries_errored")
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
    metrics.increment("queries_executed")
    metrics.observe_latency(result.elapsed_seconds)
    return {
        "columns": result.columns,
        "rows": result.rows,
        "elapsed_seconds": result.elapsed_seconds,
        "row_count": result.row_count,
        "truncated": result.truncated,
    }


@router.post("/execute")
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
@router.post("/reports", response_model=Report, status_code=201)
def create_report(body: ReportCreate) -> Report:
    try:
        return _report_store.create(body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/reports", response_model=List[Report])
def list_reports() -> List[Report]:
    return _report_store.list()


@router.get("/reports/{report_id}", response_model=Report)
def get_report(report_id: str) -> Report:
    report = _report_store.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return report


@router.put("/reports/{report_id}", response_model=Report)
def update_report(report_id: str, body: ReportCreate) -> Report:
    try:
        updated = _report_store.update(report_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if updated is None:
        raise HTTPException(status_code=404, detail="Report not found.")
    return updated


@router.delete("/reports/{report_id}", status_code=204)
def delete_report(report_id: str) -> Response:
    if not _report_store.delete(report_id):
        raise HTTPException(status_code=404, detail="Report not found.")
    return Response(status_code=204)


@router.post("/reports/{report_id}/run")
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
# Email a result (Phase 9, ADR-020): a sibling to CSV/Excel export. Reuses the
# Phase-8 mailer unchanged — no LLM and no re-query: the DataFrame is rebuilt
# from the result the client already holds, then sent through send_report_email
# (header-injection guard, allow-list, size cap, audit log all apply).
# --------------------------------------------------------------------------- #
@router.post("/reports/email")
def email_report(req: EmailReportRequest):
    # Opt-in: inert unless SMTP_USER + SMTP_PASSWORD are configured server-side.
    if not email_enabled():
        raise HTTPException(
            status_code=503,
            detail="Email is not configured on the server — set BREVO_API_KEY + EMAIL_FROM (or SMTP_USER + SMTP_PASSWORD).",
        )

    # Bound the in-memory DataFrame build before the mailer's byte-cap can reject
    # it (review finding #2): a shown result is already row-capped by /execute, so
    # an oversized payload here is abuse — reject cheaply, pre-build.
    MAX_EMAIL_ROWS, MAX_EMAIL_COLS = 100_000, 1_000
    if len(req.rows) > MAX_EMAIL_ROWS or len(req.columns) > MAX_EMAIL_COLS:
        raise HTTPException(
            status_code=400,
            detail=f"Result too large to email (limit {MAX_EMAIL_ROWS:,} rows × "
            f"{MAX_EMAIL_COLS:,} columns). Narrow the query first.",
        )

    import pandas as pd

    try:
        df = pd.DataFrame(req.rows, columns=req.columns)
    except ValueError as exc:
        # Ragged rows / column-count mismatch — a client error, not a server fault.
        raise HTTPException(status_code=400, detail=f"Result does not match columns: {exc}")

    result = send_report_email(
        to=req.to,
        subject=req.subject,
        body=req.body,
        df=df,
        attachment_format=req.attachment_format,
        cc=req.cc,
        filename=req.filename,
    )

    if result.kind == "ok":
        return {
            "status": "ok",
            "message": result.message,
            "recipients": result.recipients,
            "attachment_bytes": result.attachment_bytes,
        }
    if result.kind == "rejected":
        # User-actionable (bad recipient/domain/format/oversize) — safe verbatim.
        raise HTTPException(status_code=400, detail=result.message)
    # Transport/auth failure: the mailer already logged full detail under its own
    # error_id and returned only a generic message. Surface that exact id (not the
    # request-scoped one) so the client's reference matches the server log line —
    # returned explicitly because a contextvar set in the sync-route threadpool
    # would not reach the async exception handler. 502: the upstream send failed.
    return JSONResponse(
        status_code=502,
        content={"detail": result.message, "error_id": result.error_id},
    )


# --------------------------------------------------------------------------- #
# Email a cascading-report HTML bundle (Phase 10, ADR-026): the client posts the
# prebuilt bundle; it is sent as an .html attachment via the Phase-8 mailer
# chokepoint (allow-list, header-injection guard, size cap, audit). No LLM, no
# re-query — the same data-egress boundary as /reports/email.
# --------------------------------------------------------------------------- #
@router.post("/reports/email-bundle")
def email_report_bundle(req: EmailBundleRequest):
    # Opt-in: inert unless SMTP_USER + SMTP_PASSWORD are configured server-side.
    if not email_enabled():
        raise HTTPException(
            status_code=503,
            detail="Email is not configured on the server — set BREVO_API_KEY + EMAIL_FROM (or SMTP_USER + SMTP_PASSWORD).",
        )

    # Reject an oversized bundle cheaply, before the mailer encodes it. The mailer's
    # own byte cap (EMAIL_MAX_ATTACHMENT_MB) is the authoritative limit and maps to 400.
    MAX_BUNDLE_BYTES = 30_000_000
    if len(req.html.encode("utf-8")) > MAX_BUNDLE_BYTES:
        raise HTTPException(
            status_code=400,
            detail="Report is too large to email. Narrow it (fewer breakdowns/rows) and try again.",
        )

    result = send_html_bundle_email(
        to=req.to,
        subject=req.subject,
        body=req.body,
        html=req.html,
        cc=req.cc,
        filename=req.filename,
    )

    if result.kind == "ok":
        return {
            "status": "ok",
            "message": result.message,
            "recipients": result.recipients,
            "attachment_bytes": result.attachment_bytes,
        }
    if result.kind == "rejected":
        # User-actionable (bad recipient/domain/oversize/not configured) — safe verbatim.
        raise HTTPException(status_code=400, detail=result.message)
    # Transport/auth failure: generic message + the mailer's own error_id.
    return JSONResponse(
        status_code=502,
        content={"detail": result.message, "error_id": result.error_id},
    )


# --------------------------------------------------------------------------- #
# Export a result (Phase 9): downloadable CSV/Excel of the shown result. Excel is
# built server-side via openpyxl (no browser spreadsheet lib). No LLM, no re-query.
# --------------------------------------------------------------------------- #
@router.post("/reports/export")
def export_report(req: ExportRequest) -> Response:
    MAX_EXPORT_ROWS, MAX_EXPORT_COLS = 100_000, 1_000
    if len(req.rows) > MAX_EXPORT_ROWS or len(req.columns) > MAX_EXPORT_COLS:
        raise HTTPException(
            status_code=400,
            detail=f"Result too large to export (limit {MAX_EXPORT_ROWS:,} rows × {MAX_EXPORT_COLS:,} columns).",
        )

    import pandas as pd

    try:
        df = pd.DataFrame(req.rows, columns=req.columns)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Result does not match columns: {exc}")

    fmt = (req.format or "xlsx").strip().lower()
    # Sanitize the filename before it reaches the Content-Disposition header.
    safe = "".join(c for c in (req.filename or "report") if c.isalnum() or c in "._-")[:64] or "report"
    if fmt in ("xlsx", "xls", "excel"):
        content, media, ext = dataframe_to_excel_bytes(df), (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ), "xlsx"
    elif fmt == "csv":
        content, media, ext = dataframe_to_csv_bytes(df), "text/csv; charset=utf-8", "csv"
    else:
        raise HTTPException(status_code=400, detail="format must be 'csv' or 'xlsx'.")

    return Response(
        content=content,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="{safe}.{ext}"'},
    )


# --------------------------------------------------------------------------- #
# Templates (read-only curated EBS starter catalog)
# --------------------------------------------------------------------------- #
@router.get("/templates", response_model=List[Template])
def get_templates() -> List[Template]:
    return list_templates()


@router.get("/templates/{template_id}", response_model=Template)
def get_template_by_id(template_id: str) -> Template:
    template = get_template(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found.")
    return template


# --------------------------------------------------------------------------- #
# EBS metadata packs (read-only curated descriptions + glossary; Phase 7)
# --------------------------------------------------------------------------- #
@router.get("/packs", response_model=List[EbsPack])
def get_packs() -> List[EbsPack]:
    return list_packs()


@router.get("/packs/{module}", response_model=EbsPack)
def get_pack_by_module(module: str) -> EbsPack:
    pack = get_pack(module)
    if pack is None:
        raise HTTPException(status_code=404, detail="Unknown EBS module.")
    return pack


# --------------------------------------------------------------------------- #
# Saved schemas (data-dictionary snapshots) + live introspection
# --------------------------------------------------------------------------- #
@router.post("/schemas", response_model=SchemaRecord, status_code=201)
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


@router.get("/schemas", response_model=List[SchemaSummary])
def list_schemas() -> List[SchemaSummary]:
    return _schema_store.list()


@router.get("/schemas/{schema_id}", response_model=SchemaRecord)
def get_schema(schema_id: str) -> SchemaRecord:
    record = _schema_store.get(schema_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Schema not found.")
    return record


@router.delete("/schemas/{schema_id}", status_code=204)
def delete_schema(schema_id: str) -> Response:
    if not _schema_store.delete(schema_id):
        raise HTTPException(status_code=404, detail="Schema not found.")
    return Response(status_code=204)


@router.post("/schemas/introspect")
def introspect(req: IntrospectRequest) -> Dict[str, Any]:
    conn_cfg, _username, profile_id = _resolve_target(req.profile_id, req.connection)
    client = make_client(conn_cfg)
    try:
        if _dialect_for(conn_cfg) == "postgres":
            result = introspect_schema_postgres(client, schema=req.owner or "public")
        else:
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


@router.post("/schemas/profile")
def profile(req: ProfileRequest) -> Dict[str, Any]:
    """Phase 11 profiling: enriched Channel-A metadata + advisory + readiness, and
    optional opt-in Channel-B value-domain sampling. Every query is SELECT-only
    through the chokepoint; value domains are stored server-side only (invariant 3)."""
    conn_cfg, _username, profile_id = _resolve_target(req.profile_id, req.connection)
    client = make_client(conn_cfg)
    is_pg = _dialect_for(conn_cfg) == "postgres"
    try:
        if is_pg:
            # Postgres MVP: basic introspection (tables/columns/PK/FK). Enriched
            # profiling (indexes/stats/value-domains) + the advisory are Oracle-only
            # for now; readiness reflects only what we actually read.
            intro = introspect_schema_postgres(client, schema=req.owner or "public")
            schema_obj = intro.schema
            warnings = list(intro.warnings)
            truncated = intro.truncated
            coverage = {
                "columns": bool(schema_obj.tables),
                "primary_keys": not any("Primary keys" in w for w in warnings),
                "foreign_keys": not any("Foreign keys" in w for w in warnings),
                "indexes": False, "partitions": False, "stats": False, "unique": False,
            }
        else:
            result = profile_schema(client, owner=req.owner, table_like=req.table_like)
            schema_obj = result.schema
            warnings = list(result.warnings)
            truncated = result.truncated
            coverage = result.coverage
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - DB/connection errors (sanitized, ITM-015)
        raise _db_error(exc, "profile")

    # Channel B (opt-in, Oracle MVP): bounded value-domain sampling. Stored
    # server-side only — NEVER in the Schema/definition or any LLM context (inv 3).
    semantics: Dict[str, Any] = dict(req.semantics or {})
    if not is_pg and req.sample_value_columns:
        targets = []
        for spec in req.sample_value_columns:
            if "." in spec:
                tname, cname = spec.split(".", 1)
                targets.append((tname.strip().upper(), cname.strip().upper()))
        if targets:
            try:
                domains, vd_warnings = capture_value_domains(client, req.owner.upper(), targets)
            except Exception as exc:  # noqa: BLE001
                raise _db_error(exc, "value_domains")
            if domains:
                merged = dict(semantics.get("value_domains") or {})
                merged.update(domains)
                semantics["value_domains"] = merged
            warnings.extend(vd_warnings)

    definition = schema_to_dict(schema_obj)
    advisory = [] if is_pg else [s.model_dump() for s in build_optimization_advisory(schema_obj)]
    readiness = compute_readiness(schema_obj, semantics, coverage, req.enforcement)

    saved: Optional[Dict[str, Any]] = None
    if req.schema_id:
        record = _schema_store.update(
            req.schema_id, definition=definition, semantics=semantics,
            readiness=readiness.model_dump(), source="introspection",
        )
        if record is None:
            raise HTTPException(status_code=404, detail="Schema not found.")
        saved = record.summary().model_dump()
    elif req.save:
        name = req.name or f"{req.owner.upper()} (profiled)"
        try:
            record = _schema_store.create(
                name, definition, source="introspection", profile_id=profile_id
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        record = _schema_store.update(
            record.id, semantics=semantics, readiness=readiness.model_dump()
        )
        saved = record.summary().model_dump() if record else None

    return {
        "definition": definition,
        "table_count": len(definition.get("tables") or {}),
        "warnings": warnings,
        "truncated": truncated,
        "coverage": coverage,
        "advisory": advisory,
        "readiness": readiness.model_dump(),
        "saved": saved,
    }


@router.get("/schemas/{schema_id}/advisory")
def schema_advisory(schema_id: str) -> Dict[str, Any]:
    record = _schema_store.get(schema_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Schema not found.")
    schema = schema_from_dict(record.definition)
    return {"advisory": [s.model_dump() for s in build_optimization_advisory(schema)]}


@router.get("/schemas/{schema_id}/readiness")
def schema_readiness(schema_id: str) -> Dict[str, Any]:
    record = _schema_store.get(schema_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Schema not found.")
    if record.readiness:
        return {"readiness": record.readiness}
    # No persisted snapshot (e.g. an upload that was never profiled): recompute with
    # empty coverage so unread catalog signals show as "unavailable".
    schema = schema_from_dict(record.definition)
    readiness = compute_readiness(schema, record.semantics, {}, "soft")
    return {"readiness": readiness.model_dump()}


# The API is always served under /v1 (T-18). The root mount stays for back-compat
# in dev / tests / API-only deployments. When SERVE_SPA bundles the React app, the
# API is /v1-only (so the SPA owns the root paths) and the built dist is served.
app.include_router(router, prefix="/v1")

_SERVE_SPA = os.getenv("SERVE_SPA", "").lower() in ("1", "true", "yes")
_DIST_DIR = Path(__file__).resolve().parent.parent / "dist"

if _SERVE_SPA and (_DIST_DIR / "index.html").exists():
    from fastapi.responses import FileResponse
    from fastapi.staticfiles import StaticFiles

    _assets = _DIST_DIR / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=str(_assets)), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def _serve_spa(full_path: str):
        # Unknown /v1 API paths 404 rather than masquerading as the SPA shell.
        if full_path == "v1" or full_path.startswith("v1/"):
            raise HTTPException(status_code=404, detail="Not found.")
        candidate = _DIST_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(str(candidate))
        return FileResponse(str(_DIST_DIR / "index.html"))  # SPA client-route fallback
else:
    app.include_router(router)  # root back-compat (dev / tests / API-only)


# Run: uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
# Bind/auth/CORS guidance for networked deployments: docs/07-deployment-plan.md
# (APP_API_KEY enables auth; ALLOWED_ORIGINS restricts CORS). SERVE_SPA serves the
# built web/ SPA from <repo>/dist (Render single-service deploy).
