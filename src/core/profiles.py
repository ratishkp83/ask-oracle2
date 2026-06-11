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
import os
import threading
import uuid
from abc import ABC, abstractmethod
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from src.core.crypto import decrypt_secret, encrypt_secret
from src.core.fileio import atomic_write_json
from src.storage import DEFAULT_STORAGE_DIR

Environment = Literal["DEV", "TEST", "PROD"]


class ProfileCreate(BaseModel):
    """Inbound payload for creating a profile (carries the plaintext password)."""

    name: str = Field(..., min_length=1, max_length=120)
    host: str = Field(..., min_length=1)
    port: int = Field(1521, ge=1, le=65535)
    service_name: Optional[str] = None
    sid: Optional[str] = None
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)
    environment: Environment = "DEV"

    @model_validator(mode="after")
    def _require_service_or_sid(self) -> "ProfileCreate":
        if not (self.service_name or self.sid):
            raise ValueError("Either service_name or sid must be provided.")
        return self


class ProfilePublic(BaseModel):
    """Outbound profile representation. Never contains a password."""

    id: str
    name: str
    host: str
    port: int
    service_name: Optional[str] = None
    sid: Optional[str] = None
    username: str
    environment: Environment


class StoredProfile(BaseModel):
    """On-disk representation: like :class:`ProfilePublic` but with the cipher."""

    id: str
    name: str
    host: str
    port: int
    service_name: Optional[str] = None
    sid: Optional[str] = None
    username: str
    environment: Environment
    password_encrypted: str

    def to_public(self) -> ProfilePublic:
        return ProfilePublic(
            id=self.id,
            name=self.name,
            host=self.host,
            port=self.port,
            service_name=self.service_name,
            sid=self.sid,
            username=self.username,
            environment=self.environment,
        )


class ResolvedConnection(BaseModel):
    """Internal-only: a profile with its decrypted password, ready to connect."""

    host: str
    port: int
    service_name: Optional[str] = None
    sid: Optional[str] = None
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

    # --- persistence helpers -------------------------------------------------
    def _load(self) -> Dict[str, StoredProfile]:
        if not os.path.exists(self._path):
            return {}
        with open(self._path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        return {pid: StoredProfile(**rec) for pid, rec in raw.items()}

    def _save(self, profiles: Dict[str, StoredProfile]) -> None:
        serializable = {pid: rec.model_dump() for pid, rec in profiles.items()}
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
                host=data.host,
                port=data.port,
                service_name=data.service_name,
                sid=data.sid,
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
                host=stored.host,
                port=stored.port,
                service_name=stored.service_name,
                sid=stored.sid,
                username=stored.username,
                password=decrypt_secret(stored.password_encrypted),
            )


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
                host=data.host,
                port=data.port,
                service_name=data.service_name,
                sid=data.sid,
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
                host=stored.host,
                port=stored.port,
                service_name=stored.service_name,
                sid=stored.sid,
                username=stored.username,
                password=decrypt_secret(stored.password_encrypted),
            )
