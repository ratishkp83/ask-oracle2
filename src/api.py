from __future__ import annotations

from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, model_validator

from src.core import audit
from src.core.config import load_safety_limits
from src.core.crypto import SecretConfigError
from src.core.profiles import (
    JsonFileProfileStore,
    ProfileCreate,
    ProfilePublic,
    ProfileStore,
)
from src.core.sql_safety import SqlSafetyError, assert_safe_select
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

app = FastAPI(title="Ask Oracle Reports API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pluggable storage backend. Swap for SqliteProfileStore later without touching
# the routes below.
_store: ProfileStore = JsonFileProfileStore()


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
    api_key: Optional[str] = None
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

    @model_validator(mode="after")
    def _require_target(self) -> "SQLExecuteRequest":
        if not self.profile_id and self.connection is None:
            raise ValueError("Provide either profile_id or an inline connection.")
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
    except Exception as exc:  # noqa: BLE001 - surface a clean message to the UI
        raise HTTPException(status_code=400, detail=str(exc))
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
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc))
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
@app.post("/execute")
def execute(req: SQLExecuteRequest) -> Dict[str, Any]:
    # Resolve the connection target first so we can audit by user.
    profile_id = req.profile_id
    if profile_id:
        resolved = _store.resolve(profile_id)
        if resolved is None:
            raise HTTPException(status_code=404, detail="Profile not found.")
        conn_cfg = OracleConnectionConfig(
            host=resolved.host,
            port=resolved.port,
            service_name=resolved.service_name,
            sid=resolved.sid,
            username=resolved.username,
            password=resolved.password,
        )
        username = resolved.username
    else:
        c = req.connection  # guaranteed present by validator
        conn_cfg = OracleConnectionConfig(
            host=c.host,
            port=c.port,
            service_name=c.service_name,
            sid=c.sid,
            username=c.username,
            password=c.password,
        )
        username = c.username

    # Safety gate: reject anything that is not a provably read-only SELECT/CTE.
    safety = assert_safe_select(req.sql)
    if not safety.allowed:
        audit.audit_execution(
            source="api",
            sql=req.sql,
            allowed=False,
            profile_id=profile_id,
            username=username,
            reason=safety.reason,
        )
        raise HTTPException(status_code=400, detail=safety.reason or "Query rejected by safety layer.")

    # Narrow (never widen) the global row cap if the caller requested fewer rows.
    limits = load_safety_limits()
    if req.max_rows is not None:
        limits = limits.model_copy(update={"max_rows": max(1, min(req.max_rows, limits.max_rows))})

    client = OracleClient(conn_cfg)
    try:
        result = client.run_select(req.sql, limits=limits)
    except SqlSafetyError as exc:
        audit.audit_execution(
            source="api", sql=req.sql, allowed=False, profile_id=profile_id, username=username, reason=str(exc)
        )
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - DB/connection errors
        audit.audit_execution(
            source="api", sql=req.sql, allowed=True, profile_id=profile_id, username=username, reason="execution_error"
        )
        raise HTTPException(status_code=400, detail=str(exc))

    audit.audit_execution(
        source="api",
        sql=req.sql,
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


# Run: uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
