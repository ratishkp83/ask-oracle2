"""Schema persistence: saved data-dictionary snapshots (Phase 5, ADR-011).

A saved schema is **metadata only** — table/column/relationship structure produced
by an upload (CSV/Excel) or by live introspection. It carries **no data values and
no credentials**. Persisting it lets a dictionary survive sessions (no re-upload)
and be served read-only via the API.

The default backend is a JSON file under ``STORAGE_DIR`` (``schemas.json``).
``SchemaStore`` is an ABC so a SQLite/Postgres backend can drop in later without
touching the API, mirroring :mod:`src.core.profiles` and :mod:`src.core.reports`.

The serialized schema lives under the field ``definition`` (a plain dict produced
by :func:`src.schema.schema_to_dict`) — ``schema`` is avoided as a field name
because it shadows a Pydantic ``BaseModel`` attribute.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from src.storage import DEFAULT_STORAGE_DIR

SchemaSource = Literal["upload", "introspection"]


class SchemaSummary(BaseModel):
    """List view — no serialized schema blob."""

    id: str
    name: str
    source: SchemaSource
    profile_id: Optional[str] = None
    table_count: int
    created_at: str
    updated_at: str


class SchemaRecord(BaseModel):
    """A persisted schema snapshot (metadata only)."""

    id: str
    name: str
    source: SchemaSource = "upload"
    profile_id: Optional[str] = None
    table_count: int = 0
    created_at: str
    updated_at: str
    definition: Dict[str, Any] = Field(default_factory=dict)

    def summary(self) -> SchemaSummary:
        return SchemaSummary(
            id=self.id,
            name=self.name,
            source=self.source,
            profile_id=self.profile_id,
            table_count=self.table_count,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_record(
    name: str, definition: Dict[str, Any], source: SchemaSource, profile_id: Optional[str]
) -> SchemaRecord:
    now = _now_iso()
    tables = definition.get("tables") if isinstance(definition, dict) else None
    return SchemaRecord(
        id=uuid.uuid4().hex,
        name=name,
        source=source,
        profile_id=profile_id,
        table_count=len(tables) if isinstance(tables, dict) else 0,
        created_at=now,
        updated_at=now,
        definition=definition,
    )


class SchemaStore(ABC):
    @abstractmethod
    def create(
        self,
        name: str,
        definition: Dict[str, Any],
        *,
        source: SchemaSource = "upload",
        profile_id: Optional[str] = None,
    ) -> SchemaRecord: ...

    @abstractmethod
    def list(self) -> List[SchemaSummary]: ...

    @abstractmethod
    def get(self, schema_id: str) -> Optional[SchemaRecord]: ...

    @abstractmethod
    def delete(self, schema_id: str) -> bool: ...


class JsonFileSchemaStore(SchemaStore):
    """File-backed schema store. Thread-safe for a single process."""

    def __init__(self, path: Optional[str] = None) -> None:
        self._path = path or os.path.join(DEFAULT_STORAGE_DIR, "schemas.json")
        self._lock = threading.Lock()

    def _load(self) -> Dict[str, SchemaRecord]:
        if not os.path.exists(self._path):
            return {}
        with open(self._path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        return {sid: SchemaRecord(**rec) for sid, rec in raw.items()}

    def _save(self, records: Dict[str, SchemaRecord]) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        serializable = {sid: rec.model_dump() for sid, rec in records.items()}
        with open(self._path, "w", encoding="utf-8") as fh:
            json.dump(serializable, fh, indent=2)

    def create(
        self,
        name: str,
        definition: Dict[str, Any],
        *,
        source: SchemaSource = "upload",
        profile_id: Optional[str] = None,
    ) -> SchemaRecord:
        with self._lock:
            records = self._load()
            if any(r.name == name for r in records.values()):
                raise ValueError(f"A schema named '{name}' already exists.")
            record = _new_record(name, definition, source, profile_id)
            records[record.id] = record
            self._save(records)
            return record

    def list(self) -> List[SchemaSummary]:
        with self._lock:
            return [r.summary() for r in sorted(self._load().values(), key=lambda r: r.name)]

    def get(self, schema_id: str) -> Optional[SchemaRecord]:
        with self._lock:
            return self._load().get(schema_id)

    def delete(self, schema_id: str) -> bool:
        with self._lock:
            records = self._load()
            if schema_id not in records:
                return False
            del records[schema_id]
            self._save(records)
            return True


class InMemorySchemaStore(SchemaStore):
    """Ephemeral store (lost on restart). Handy for tests and demos."""

    def __init__(self) -> None:
        self._records: Dict[str, SchemaRecord] = {}
        self._lock = threading.Lock()

    def create(
        self,
        name: str,
        definition: Dict[str, Any],
        *,
        source: SchemaSource = "upload",
        profile_id: Optional[str] = None,
    ) -> SchemaRecord:
        with self._lock:
            if any(r.name == name for r in self._records.values()):
                raise ValueError(f"A schema named '{name}' already exists.")
            record = _new_record(name, definition, source, profile_id)
            self._records[record.id] = record
            return record

    def list(self) -> List[SchemaSummary]:
        with self._lock:
            return [r.summary() for r in sorted(self._records.values(), key=lambda r: r.name)]

    def get(self, schema_id: str) -> Optional[SchemaRecord]:
        with self._lock:
            return self._records.get(schema_id)

    def delete(self, schema_id: str) -> bool:
        with self._lock:
            return self._records.pop(schema_id, None) is not None
