"""Connection profiles: named Oracle connections with encrypted credentials.

Profiles replace the single cleartext ``connection.json`` from Phase 1. The
password is encrypted at rest (see :mod:`src.core.crypto`) and is never exposed
through :class:`ProfilePublic`, which is what the API returns. Only the internal
:meth:`ProfileStore.resolve` returns the decrypted password, for the sole
purpose of opening a connection server-side.

The default backend is a JSON file under ``STORAGE_DIR``. ``ProfileStore`` is an
ABC so a SQLite/Postgres backend can be dropped in later without touching the
API layer.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from src.core.crypto import decrypt_secret, encrypt_secret
from src.core.errors import log_error, new_error_id
from src.core.fileio import atomic_write_json
from src.core.logging_config import get_logger
from src.storage import DEFAULT_STORAGE_DIR

Environment = Literal["DEV", "TEST", "PROD"]
Engine = Literal["oracle", "postgres"]


class ProfileCreate(BaseModel):
    """Inbound payload for creating a profile (carries the plaintext password)."""

    name: str = Field(..., min_length=1, max_length=120)
    # Multi-engine (Phase 11): "oracle" (default) | "postgres" (Supabase). Postgres
    # uses `database` (+ optional `sslmode`); Oracle uses `service_name`/`sid`.
    # `current_schema` doubles as the Postgres search_path.
    engine: Engine = "oracle"
    host: str = Field(..., min_length=1)
    port: int = Field(1521, ge=1, le=65535)
    service_name: Optional[str] = None
    sid: Optional[str] = None
    database: Optional[str] = None
    sslmode: Optional[str] = None
    current_schema: Optional[str] = Field(None, max_length=128)
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    environment: Environment = "DEV"

    @model_validator(mode="after")
    def _require_target(self) -> "ProfileCreate":
        if self.engine == "postgres":
            if not self.database:
                raise ValueError("A database name is required for a PostgreSQL connection.")
        elif not (self.service_name or self.sid):
            raise ValueError("Either service_name or sid must be provided.")
        return self


class ProfilePublic(BaseModel):
    """Outbound profile representation. Never contains a password."""

    id: str
    name: str
    engine: Engine = "oracle"
    host: str
    port: int
    service_name: Optional[str] = None
    sid: Optional[str] = None
    database: Optional[str] = None
    sslmode: Optional[str] = None
    current_schema: Optional[str] = None
    username: str
    environment: Environment


class StoredProfile(BaseModel):
    """On-disk representation: like :class:`ProfilePublic` but with the cipher."""

    id: str
    name: str
    engine: Engine = "oracle"
    host: str
    port: int
    service_name: Optional[str] = None
    sid: Optional[str] = None
    database: Optional[str] = None
    sslmode: Optional[str] = None
    current_schema: Optional[str] = None
    username: str
    environment: Environment
    password_encrypted: str

    def to_public(self) -> ProfilePublic:
        return ProfilePublic(
            id=self.id,
            name=self.name,
            engine=self.engine,
            host=self.host,
            port=self.port,
            service_name=self.service_name,
            sid=self.sid,
            database=self.database,
            sslmode=self.sslmode,
            current_schema=self.current_schema,
            username=self.username,
            environment=self.environment,
        )


class ResolvedConnection(BaseModel):
    """Internal-only: a profile with its decrypted password, ready to connect."""

    engine: Engine = "oracle"
    host: str
    port: int
    service_name: Optional[str] = None
    sid: Optional[str] = None
    database: Optional[str] = None
    sslmode: Optional[str] = None
    current_schema: Optional[str] = None
    username: str
    password: str


class ProfileStore(ABC):
    @abstractmethod
    def create(self, data: ProfileCreate) -> ProfilePublic: ...

    @abstractmethod
    def list(self) -> List[ProfilePublic]: ...

    @abstractmethod
    def get(self, profile_id: str) -> Optional[ProfilePublic]: ...

    @abstractmethod
    def delete(self, profile_id: str) -> bool: ...

    @abstractmethod
    def resolve(self, profile_id: str) -> Optional[ResolvedConnection]: ...


class JsonFileProfileStore(ProfileStore):
    """File-backed profile store. Thread-safe for a single process."""

    def __init__(self, path: Optional[str] = None) -> None:
        self._path = path or os.path.join(DEFAULT_STORAGE_DIR, "profiles.json")
        self._lock = threading.Lock()
        self._quarantined: Dict[str, Any] = {}

    # --- persistence helpers -------------------------------------------------
    def _load(self) -> Dict[str, StoredProfile]:
        if not os.path.exists(self._path):
            return {}
        with open(self._path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        profiles: Dict[str, StoredProfile] = {}
        quarantined: Dict[str, Any] = {}
        for pid, rec in raw.items():
            try:
                profiles[pid] = StoredProfile(**rec)
            except (ValueError, TypeError) as exc:  # corrupt record: quarantine (ADR-014)
                quarantined[pid] = rec
                if pid not in self._quarantined:  # log once per process, not per load
                    log_error(
                        ValueError(
                            f"Corrupt profile record '{pid}' quarantined "
                            f"({type(exc).__name__}); not served, preserved on save"
                        ),
                        context="profile_store.corrupt_record",
                        error_id=new_error_id(),
                        event="corrupt_record",
                        level=logging.WARNING,
                    )
        self._quarantined = quarantined
        return profiles

    def _save(self, profiles: Dict[str, StoredProfile]) -> None:
        serializable: Dict[str, Any] = {pid: rec.model_dump() for pid, rec in profiles.items()}
        # Quarantined records ride along verbatim — never silently dropped (ADR-014).
        for pid, rec in self._quarantined.items():
            serializable.setdefault(pid, rec)
        atomic_write_json(self._path, serializable)

    # --- ProfileStore API ----------------------------------------------------
    def create(self, data: ProfileCreate) -> ProfilePublic:
        with self._lock:
            profiles = self._load()
            if any(p.name == data.name for p in profiles.values()):
                raise ValueError(f"A profile named '{data.name}' already exists.")
            profile_id = uuid.uuid4().hex
            stored = StoredProfile(
                id=profile_id,
                name=data.name,
                engine=data.engine,
                host=data.host,
                port=data.port,
                service_name=data.service_name,
                sid=data.sid,
                database=data.database,
                sslmode=data.sslmode,
                current_schema=data.current_schema,
                username=data.username,
                environment=data.environment,
                password_encrypted=encrypt_secret(data.password),
            )
            profiles[profile_id] = stored
            self._save(profiles)
            return stored.to_public()

    def list(self) -> List[ProfilePublic]:
        with self._lock:
            return [p.to_public() for p in sorted(self._load().values(), key=lambda p: p.name)]

    def get(self, profile_id: str) -> Optional[ProfilePublic]:
        with self._lock:
            stored = self._load().get(profile_id)
            return stored.to_public() if stored else None

    def delete(self, profile_id: str) -> bool:
        with self._lock:
            profiles = self._load()
            if profile_id not in profiles:
                return False
            del profiles[profile_id]
            self._save(profiles)
            return True

    def resolve(self, profile_id: str) -> Optional[ResolvedConnection]:
        with self._lock:
            stored = self._load().get(profile_id)
            if stored is None:
                return None
            return ResolvedConnection(
                engine=stored.engine,
                host=stored.host,
                port=stored.port,
                service_name=stored.service_name,
                sid=stored.sid,
                database=stored.database,
                sslmode=stored.sslmode,
                current_schema=stored.current_schema,
                username=stored.username,
                password=decrypt_secret(stored.password_encrypted),
            )


def seed_profile_from_env(store: ProfileStore) -> Optional[ProfilePublic]:
    """Idempotently (re)create a connection profile from ``SEED_*`` env vars.

    Lets a stateless deploy whose disk is wiped on every restart (e.g. Render's
    free tier) restore its database connection automatically on boot, instead of
    an operator re-adding it by hand each time. The password lives only in the
    platform's environment (never the repo) and is encrypted at rest by the
    store exactly like a UI-created profile — invariant 4 holds.

    No-op unless ``SEED_HOST`` + ``SEED_USERNAME`` + ``SEED_PASSWORD`` are all
    set. If a profile named ``SEED_PROFILE_NAME`` already exists (e.g. on a
    persistent disk) it is left untouched, so this is safe to call on every
    boot. Never raises: a bad seed config logs a warning and the app starts
    normally.
    """
    host = os.getenv("SEED_HOST")
    username = os.getenv("SEED_USERNAME")
    password = os.getenv("SEED_PASSWORD")
    if not (host and username and password):
        return None

    log = get_logger("profiles")
    name = os.getenv("SEED_PROFILE_NAME", "Seeded connection")
    engine = os.getenv("SEED_ENGINE", "postgres").strip().lower()
    if engine not in ("oracle", "postgres"):
        engine = "postgres"
    is_pg = engine == "postgres"
    try:
        if any(p.name == name for p in store.list()):
            log.info("Seed profile already present; leaving it untouched",
                     extra={"extra_fields": {"name": name}})
            return None
        data = ProfileCreate(
            name=name,
            engine=engine,  # type: ignore[arg-type]  # validated by the model
            host=host,
            port=int(os.getenv("SEED_PORT", "5432" if is_pg else "1521")),
            database=os.getenv("SEED_DATABASE"),
            sslmode=os.getenv("SEED_SSLMODE", "require") if is_pg else os.getenv("SEED_SSLMODE"),
            current_schema=os.getenv("SEED_SCHEMA", "public") if is_pg else os.getenv("SEED_SCHEMA"),
            service_name=os.getenv("SEED_SERVICE_NAME"),
            sid=os.getenv("SEED_SID"),
            username=username,
            password=password,
            environment=os.getenv("SEED_ENVIRONMENT", "DEV"),  # type: ignore[arg-type]
        )
        created = store.create(data)
        log.info("Seeded a connection profile from env",
                 extra={"extra_fields": {"name": name, "engine": engine, "host": host}})
        return created
    except Exception as exc:  # never block startup on a bad seed config
        # Log the exception TYPE only — never str(exc), which could echo the password.
        log.warning("Could not seed a connection profile from env",
                    extra={"extra_fields": {"error_type": type(exc).__name__, "name": name}})
        return None


class InMemoryProfileStore(ProfileStore):
    """Ephemeral store (lost on restart). Handy for tests and demos."""

    def __init__(self) -> None:
        self._profiles: Dict[str, StoredProfile] = {}
        self._lock = threading.Lock()

    def create(self, data: ProfileCreate) -> ProfilePublic:
        with self._lock:
            if any(p.name == data.name for p in self._profiles.values()):
                raise ValueError(f"A profile named '{data.name}' already exists.")
            profile_id = uuid.uuid4().hex
            stored = StoredProfile(
                id=profile_id,
                name=data.name,
                engine=data.engine,
                host=data.host,
                port=data.port,
                service_name=data.service_name,
                sid=data.sid,
                database=data.database,
                sslmode=data.sslmode,
                current_schema=data.current_schema,
                username=data.username,
                environment=data.environment,
                password_encrypted=encrypt_secret(data.password),
            )
            self._profiles[profile_id] = stored
            return stored.to_public()

    def list(self) -> List[ProfilePublic]:
        with self._lock:
            return [p.to_public() for p in sorted(self._profiles.values(), key=lambda p: p.name)]

    def get(self, profile_id: str) -> Optional[ProfilePublic]:
        with self._lock:
            stored = self._profiles.get(profile_id)
            return stored.to_public() if stored else None

    def delete(self, profile_id: str) -> bool:
        with self._lock:
            return self._profiles.pop(profile_id, None) is not None

    def resolve(self, profile_id: str) -> Optional[ResolvedConnection]:
        with self._lock:
            stored = self._profiles.get(profile_id)
            if stored is None:
                return None
            return ResolvedConnection(
                engine=stored.engine,
                host=stored.host,
                port=stored.port,
                service_name=stored.service_name,
                sid=stored.sid,
                database=stored.database,
                sslmode=stored.sslmode,
                current_schema=stored.current_schema,
                username=stored.username,
                password=decrypt_secret(stored.password_encrypted),
            )
