"""Saved reports: named, parameterized, profile-bindable SELECT queries.

A report is a saved SELECT/CTE plus optional **typed parameters** that are passed
to Oracle as **bind variables** at run time — never interpolated into the SQL
string (see :mod:`src.db` ``validate_binds`` and ADR-007). Reports may carry a
default connection profile (overridable at run time) and provenance back to the
template they were created from.

The default backend is a JSON file under ``STORAGE_DIR`` (the same
``reports.json`` used by the Phase-1 storage helper). ``ReportStore`` is an ABC so
a SQLite/Postgres backend can be dropped in later without touching the API layer,
mirroring :mod:`src.core.profiles`.

Legacy migration: the Phase-1 shape was ``{ <name>: {"sql": "..."} }``. On load,
any record lacking ``id``/``name`` is converted to a :class:`Report` v2 and the
file is rewritten once (idempotent thereafter).
"""

from __future__ import annotations

import json
import math
import os
import re
import threading
import uuid
from abc import ABC, abstractmethod
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from src.core.fileio import atomic_write_json
from src.storage import DEFAULT_STORAGE_DIR

ParamType = Literal["string", "number", "date"]

# Oracle bind/identifier names: a letter or underscore, then word chars; capped at
# 30 to stay within the classic Oracle identifier limit.
_BIND_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_BIND_NAME_MAX = 30


class ReportParam(BaseModel):
    """A typed, named report parameter, bound as ``:name`` at run time."""

    name: str = Field(..., min_length=1, max_length=_BIND_NAME_MAX)
    label: str = ""
    type: ParamType = "string"
    required: bool = True
    default: Optional[Any] = None

    @field_validator("name")
    @classmethod
    def _valid_bind_name(cls, v: str) -> str:
        if not _BIND_NAME_RE.match(v):
            raise ValueError(
                f"Parameter name '{v}' is invalid; use letters, digits and underscores "
                "(must start with a letter or underscore)."
            )
        return v

    @model_validator(mode="after")
    def _default_label(self) -> "ReportParam":
        if not self.label:
            self.label = self.name
        return self


class ReportCreate(BaseModel):
    """Inbound payload for creating/updating a report (no id/timestamps)."""

    name: str = Field(..., min_length=1, max_length=120)
    description: str = ""
    sql: str = ""
    parameters: List[ReportParam] = Field(default_factory=list)
    default_profile_id: Optional[str] = None
    template_id: Optional[str] = None


class Report(BaseModel):
    """Persisted report (v2 shape)."""

    id: str
    name: str
    description: str = ""
    sql: str = ""
    parameters: List[ReportParam] = Field(default_factory=list)
    default_profile_id: Optional[str] = None
    template_id: Optional[str] = None
    created_at: str
    updated_at: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_report(data: ReportCreate, *, report_id: Optional[str] = None) -> Report:
    now = _now_iso()
    return Report(
        id=report_id or uuid.uuid4().hex,
        name=data.name,
        description=data.description,
        sql=data.sql,
        parameters=data.parameters,
        default_profile_id=data.default_profile_id,
        template_id=data.template_id,
        created_at=now,
        updated_at=now,
    )


# --------------------------------------------------------------------------- #
# Bind coercion (run time)
# --------------------------------------------------------------------------- #
def _coerce_value(ptype: ParamType, name: str, value: Any) -> Any:
    if ptype == "number":
        if isinstance(value, bool):
            raise ValueError(f"Parameter '{name}' must be a number.")
        if isinstance(value, (int, float)):
            num: Any = value
        else:
            s = str(value).strip()
            if re.fullmatch(r"[+-]?\d+", s):
                num = int(s)
            else:
                try:
                    num = float(s)
                except ValueError:
                    raise ValueError(f"Parameter '{name}' must be a number.")
        if isinstance(num, float) and not math.isfinite(num):
            raise ValueError(f"Parameter '{name}' must be a finite number.")
        return num
    if ptype == "date":
        if isinstance(value, (date, datetime)):
            return value
        try:
            return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
        except ValueError:
            raise ValueError(f"Parameter '{name}' must be a date (YYYY-MM-DD).")
    return str(value)


def coerce_report_binds(
    parameters: List[ReportParam], raw_values: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Build the bind map for a report run from user-supplied raw values.

    Applies defaults, enforces ``required``, and coerces each value to its
    declared type. Unknown keys (not declared as parameters) are rejected so a
    caller cannot smuggle extra binds. The result is still passed through
    :func:`src.db.validate_binds` at the chokepoint.
    """
    raw_values = raw_values or {}
    declared = {p.name for p in parameters}
    unknown = set(raw_values) - declared
    if unknown:
        raise ValueError(f"Unknown parameter(s): {', '.join(sorted(unknown))}.")

    binds: Dict[str, Any] = {}
    for p in parameters:
        if p.name in raw_values and raw_values[p.name] not in (None, ""):
            value: Any = raw_values[p.name]
        elif p.default is not None:
            value = p.default
        elif p.required:
            raise ValueError(f"Missing required parameter '{p.label or p.name}'.")
        else:
            continue  # optional with no value -> do not bind
        binds[p.name] = _coerce_value(p.type, p.name, value)
    return binds


# --------------------------------------------------------------------------- #
# Store
# --------------------------------------------------------------------------- #
class ReportStore(ABC):
    @abstractmethod
    def create(self, data: ReportCreate) -> Report: ...

    @abstractmethod
    def list(self) -> List[Report]: ...

    @abstractmethod
    def get(self, report_id: str) -> Optional[Report]: ...

    @abstractmethod
    def update(self, report_id: str, data: ReportCreate) -> Optional[Report]: ...

    @abstractmethod
    def delete(self, report_id: str) -> bool: ...


def _deserialize(raw: Dict[str, Any]) -> "tuple[Dict[str, Report], bool]":
    """Return (reports-by-id, migrated?) tolerating the legacy ``{name: {sql}}``."""
    reports: Dict[str, Report] = {}
    migrated = False
    for key, rec in raw.items():
        if isinstance(rec, dict) and "id" in rec and "name" in rec:
            report = Report(**rec)
            reports[report.id] = report
        else:
            sql = rec.get("sql", "") if isinstance(rec, dict) else str(rec)
            report = _new_report(ReportCreate(name=str(key), sql=sql))
            reports[report.id] = report
            migrated = True
    return reports, migrated


class JsonFileReportStore(ReportStore):
    """File-backed report store. Thread-safe for a single process."""

    def __init__(self, path: Optional[str] = None) -> None:
        self._path = path or os.path.join(DEFAULT_STORAGE_DIR, "reports.json")
        self._lock = threading.Lock()

    # --- persistence helpers -------------------------------------------------
    def _load_locked(self) -> Dict[str, Report]:
        """Load (migrating the legacy shape in place). Caller holds the lock."""
        if not os.path.exists(self._path):
            return {}
        with open(self._path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        reports, migrated = _deserialize(raw)
        if migrated:
            self._save_locked(reports)
        return reports

    def _save_locked(self, reports: Dict[str, Report]) -> None:
        serializable = {rid: rec.model_dump() for rid, rec in reports.items()}
        atomic_write_json(self._path, serializable, default=str)

    # --- ReportStore API -----------------------------------------------------
    def create(self, data: ReportCreate) -> Report:
        with self._lock:
            reports = self._load_locked()
            if any(r.name == data.name for r in reports.values()):
                raise ValueError(f"A report named '{data.name}' already exists.")
            report = _new_report(data)
            reports[report.id] = report
            self._save_locked(reports)
            return report

    def list(self) -> List[Report]:
        with self._lock:
            return sorted(self._load_locked().values(), key=lambda r: r.name)

    def get(self, report_id: str) -> Optional[Report]:
        with self._lock:
            return self._load_locked().get(report_id)

    def update(self, report_id: str, data: ReportCreate) -> Optional[Report]:
        with self._lock:
            reports = self._load_locked()
            existing = reports.get(report_id)
            if existing is None:
                return None
            if any(r.name == data.name and rid != report_id for rid, r in reports.items()):
                raise ValueError(f"A report named '{data.name}' already exists.")
            updated = Report(
                id=existing.id,
                name=data.name,
                description=data.description,
                sql=data.sql,
                parameters=data.parameters,
                default_profile_id=data.default_profile_id,
                template_id=data.template_id,
                created_at=existing.created_at,
                updated_at=_now_iso(),
            )
            reports[report_id] = updated
            self._save_locked(reports)
            return updated

    def delete(self, report_id: str) -> bool:
        with self._lock:
            reports = self._load_locked()
            if report_id not in reports:
                return False
            del reports[report_id]
            self._save_locked(reports)
            return True


class InMemoryReportStore(ReportStore):
    """Ephemeral store (lost on restart). Handy for tests and demos."""

    def __init__(self) -> None:
        self._reports: Dict[str, Report] = {}
        self._lock = threading.Lock()

    def create(self, data: ReportCreate) -> Report:
        with self._lock:
            if any(r.name == data.name for r in self._reports.values()):
                raise ValueError(f"A report named '{data.name}' already exists.")
            report = _new_report(data)
            self._reports[report.id] = report
            return report

    def list(self) -> List[Report]:
        with self._lock:
            return sorted(self._reports.values(), key=lambda r: r.name)

    def get(self, report_id: str) -> Optional[Report]:
        with self._lock:
            return self._reports.get(report_id)

    def update(self, report_id: str, data: ReportCreate) -> Optional[Report]:
        with self._lock:
            existing = self._reports.get(report_id)
            if existing is None:
                return None
            if any(r.name == data.name and rid != report_id for rid, r in self._reports.items()):
                raise ValueError(f"A report named '{data.name}' already exists.")
            updated = Report(
                id=existing.id,
                name=data.name,
                description=data.description,
                sql=data.sql,
                parameters=data.parameters,
                default_profile_id=data.default_profile_id,
                template_id=data.template_id,
                created_at=existing.created_at,
                updated_at=_now_iso(),
            )
            self._reports[report_id] = updated
            return updated

    def delete(self, report_id: str) -> bool:
        with self._lock:
            return self._reports.pop(report_id, None) is not None
