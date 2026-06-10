from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import oracledb

from src.core.config import SafetyLimits, load_safety_limits
from src.core.sql_safety import SqlSafetyError, assert_safe_select, is_safe_select

# Re-exported so existing imports (`from src.db import is_safe_select`) keep working.
__all__ = [
    "OracleConnectionConfig",
    "build_dsn",
    "is_safe_select",
    "validate_binds",
    "QueryResult",
    "OracleClient",
]

# Bind variables (Phase 4) are passed to the driver as *values*, never spliced
# into the SQL text — so they cannot alter the parsed statement or escape the
# SELECT/CTE-only guarantee. validate_binds is a fail-closed backstop at the
# chokepoint: bind names must be plain identifiers and values must be scalars.
_BIND_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_BIND_NAME_MAX = 30
_ALLOWED_BIND_TYPES = (str, int, float, bool, date, datetime)


def validate_binds(binds: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate a bind map (or None) and return a safe dict for ``cur.execute``.

    Raises :class:`SqlSafetyError` for a non-mapping, an invalid bind name, or a
    non-scalar value (dict/list/object) — anything that could carry structure
    rather than a plain value.
    """
    if binds is None:
        return {}
    if not isinstance(binds, dict):
        raise SqlSafetyError("Binds must be a mapping of name to scalar value.")
    for name, value in binds.items():
        if not isinstance(name, str) or len(name) > _BIND_NAME_MAX or not _BIND_NAME_RE.match(name):
            raise SqlSafetyError(f"Invalid bind name: {name!r}.")
        if value is None:
            continue
        if not isinstance(value, _ALLOWED_BIND_TYPES):
            raise SqlSafetyError(
                f"Bind '{name}' must be a scalar (str/number/date), got {type(value).__name__}."
            )
        # Reject non-finite numbers (NaN/Infinity) — never valid for an Oracle NUMBER.
        if isinstance(value, float) and not math.isfinite(value):
            raise SqlSafetyError(f"Bind '{name}' must be a finite number.")
    return binds


@dataclass
class OracleConnectionConfig:
    host: str
    port: int
    service_name: Optional[str]
    sid: Optional[str]
    username: str
    password: str


@dataclass
class QueryResult:
    columns: List[str]
    rows: List[Tuple[Any, ...]]
    elapsed_seconds: float
    truncated: bool
    row_count: int


def build_dsn(host: str, port: int, service_name: Optional[str] = None, sid: Optional[str] = None) -> str:
    if service_name:
        return oracledb.makedsn(host=host, port=port, service_name=service_name)
    if sid:
        return oracledb.makedsn(host=host, port=port, sid=sid)
    raise ValueError("Either service_name or sid must be provided for DSN")


def _approx_row_bytes(row: Tuple[Any, ...]) -> int:
    """Cheap upper-ish estimate of a row's serialized size for result-size caps."""
    total = 0
    for value in row:
        if value is None:
            total += 1
        else:
            try:
                total += len(str(value))
            except Exception:  # noqa: BLE001 - never let sizing break a query
                total += 8
    return total


class OracleClient:
    def __init__(self, config: OracleConnectionConfig):
        self.config = config
        # python-oracledb defaults to thin mode; do not initialize thick client.

    def _connect(self):
        dsn = build_dsn(
            host=self.config.host,
            port=self.config.port,
            service_name=self.config.service_name,
            sid=self.config.sid,
        )
        return oracledb.connect(user=self.config.username, password=self.config.password, dsn=dsn)

    def run_select(
        self,
        sql: str,
        limits: Optional[SafetyLimits] = None,
        binds: Optional[Dict[str, Any]] = None,
    ) -> QueryResult:
        """Validate ``sql`` through the safety layer and execute it under limits.

        ``binds`` (Phase 4) are passed to the driver as bind variables, never
        interpolated into ``sql``. Raises :class:`SqlSafetyError` if the query is
        not a safe SELECT/CTE or if the binds are not name→scalar.
        """
        result = assert_safe_select(sql)
        if not result.allowed:
            raise SqlSafetyError(result.reason or "Only SELECT/CTE queries are allowed.")
        safe_binds = validate_binds(binds)

        limits = limits or load_safety_limits()
        start = time.perf_counter()
        with self._connect() as conn:
            # Cap server-side execution time where the driver supports it.
            try:
                conn.call_timeout = int(limits.max_execution_seconds * 1000)
            except Exception:  # noqa: BLE001 - not fatal if unsupported
                pass
            with conn.cursor() as cur:
                cur.execute(sql, safe_binds)
                columns = [d[0] for d in cur.description] if cur.description else []
                rows: List[Tuple[Any, ...]] = []
                total_bytes = 0
                truncated = False
                while True:
                    row = cur.fetchone()
                    if row is None:
                        break
                    rows.append(row)
                    total_bytes += _approx_row_bytes(row)
                    if len(rows) >= limits.max_rows or total_bytes >= limits.max_result_bytes:
                        # Peek one more row to report whether output was truncated.
                        if cur.fetchone() is not None:
                            truncated = True
                        break
        elapsed = time.perf_counter() - start
        return QueryResult(
            columns=columns,
            rows=rows,
            elapsed_seconds=elapsed,
            truncated=truncated,
            row_count=len(rows),
        )

    def execute_query(
        self, sql: str, max_rows: Optional[int] = None
    ) -> Tuple[List[str], List[Tuple[Any, ...]], float]:
        """Backwards-compatible wrapper returning ``(columns, rows, elapsed)``.

        Applies the configured :class:`SafetyLimits`; an explicit ``max_rows``
        narrows (never widens) the global row cap.
        """
        limits = load_safety_limits()
        if max_rows is not None:
            limits = limits.model_copy(update={"max_rows": max(1, min(max_rows, limits.max_rows))})
        result = self.run_select(sql, limits=limits)
        return result.columns, result.rows, result.elapsed_seconds
