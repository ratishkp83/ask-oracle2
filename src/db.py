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
    "expand_list_binds",
    "validate_schema_name",
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


def _validate_scalar(name: str, value: Any, index: Optional[int] = None) -> None:
    """Raise SqlSafetyError if *value* is not an acceptable Oracle bind scalar."""
    label = f"{name}[{index}]" if index is not None else name
    if value is None:
        return
    if isinstance(value, list):
        raise SqlSafetyError(f"Bind '{label}' is nested; only flat lists of scalars are allowed.")
    if not isinstance(value, _ALLOWED_BIND_TYPES):
        raise SqlSafetyError(
            f"Bind '{label}' must be a scalar (str/number/date), got {type(value).__name__}."
        )
    if isinstance(value, float) and not math.isfinite(value):
        raise SqlSafetyError(f"Bind '{label}' must be a finite number.")


def validate_binds(binds: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate a bind map (or None) and return a safe dict ready for expansion.

    Scalars (str/int/float/bool/date/datetime/None) are accepted as-is.
    Non-empty flat lists of scalars are accepted for IN-clause expansion via
    :func:`expand_list_binds`. Empty lists, nested structures, and dicts are
    rejected with :class:`SqlSafetyError`.
    """
    if binds is None:
        return {}
    if not isinstance(binds, dict):
        raise SqlSafetyError("Binds must be a mapping of name to scalar value.")
    for name, value in binds.items():
        if not isinstance(name, str) or len(name) > _BIND_NAME_MAX or not _BIND_NAME_RE.match(name):
            raise SqlSafetyError(f"Invalid bind name: {name!r}.")
        if isinstance(value, list):
            if not value:
                raise SqlSafetyError(
                    f"Bind '{name}' is an empty list; Oracle does not support IN ()."
                )
            for i, item in enumerate(value):
                _validate_scalar(name, item, index=i)
        else:
            _validate_scalar(name, value)
    return binds



def expand_list_binds(sql: str, binds: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """Expand list-valued binds into individual :name_0, :name_1, ... placeholders.

    Call this **after** :func:`validate_binds` and **before** ``cur.execute``.
    The safety check (:func:`assert_safe_select`) must run on the *original* SQL
    text and is unaffected by this transformation.

    Scalar binds pass through unchanged. For each list bind:
    - The SQL token ``:name`` is replaced by ``:name_0, :name_1, ...``
    - The returned binds dict contains ``name_0``, ``name_1``, ... instead.

    Raises :class:`SqlSafetyError` if an expanded placeholder name would exceed
    the 30-character Oracle identifier limit.
    """
    expanded: Dict[str, Any] = {}
    scalar_names = {n for n, v in binds.items() if not isinstance(v, list)}

    for name, value in binds.items():
        if not isinstance(value, list):
            expanded[name] = value
            continue
        child_names = [f"{name}_{i}" for i in range(len(value))]
        for cn in child_names:
            if len(cn) > _BIND_NAME_MAX:
                raise SqlSafetyError(
                    f"Expanded bind name '{cn}' ({len(cn)} chars) exceeds the "
                    f"{_BIND_NAME_MAX}-char Oracle limit. Shorten '{name}' or reduce "
                    "the list length."
                )
            if cn in scalar_names:
                raise SqlSafetyError(
                    f"Expanded bind name '{cn}' collides with an existing scalar bind. "
                    f"Rename the list bind '{name}'."
                )
        placeholder = ", ".join(f":{cn}" for cn in child_names)
        pattern = r"(?<![:\w]):" + re.escape(name) + r"(?!\w)"
        sql = re.sub(pattern, placeholder, sql)
        for cn, item in zip(child_names, value):
            expanded[cn] = item
    return sql, expanded


# A default schema (ADR-018) cannot be a bind variable, so it is interpolated into
# ALTER SESSION SET CURRENT_SCHEMA. This fail-closed check restricts it to the Oracle
# identifier charset (a letter, then letters/digits/_/$/#), so it cannot inject SQL.
_SCHEMA_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]*$")
_SCHEMA_NAME_MAX = 128


def validate_schema_name(name: str) -> str:
    """Return a validated Oracle schema identifier, or raise :class:`SqlSafetyError`."""
    candidate = (name or "").strip()
    if not candidate or len(candidate) > _SCHEMA_NAME_MAX or not _SCHEMA_NAME_RE.match(candidate):
        raise SqlSafetyError(f"Invalid schema name: {name!r}.")
    return candidate


@dataclass
class OracleConnectionConfig:
    host: str
    port: int
    service_name: Optional[str]
    sid: Optional[str]
    username: str
    password: str
    # Optional default schema (ADR-018): when set, the session runs
    # ALTER SESSION SET CURRENT_SCHEMA so unqualified table names resolve here.
    current_schema: Optional[str] = None


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
        conn = oracledb.connect(user=self.config.username, password=self.config.password, dsn=dsn)
        if self.config.current_schema:
            # Resolve unqualified table names against this schema — e.g. a least-privilege
            # read-only account with grants on a business schema (ADR-009/ADR-018). ALTER
            # SESSION SET CURRENT_SCHEMA is a session setting (no data change) and runs at
            # connect time, outside the SELECT-only user-query chokepoint.
            schema = validate_schema_name(self.config.current_schema)
            with conn.cursor() as cur:
                cur.execute(f"ALTER SESSION SET CURRENT_SCHEMA = {schema}")
        return conn

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
        exec_sql, exec_binds = expand_list_binds(sql, safe_binds)

        limits = limits or load_safety_limits()
        start = time.perf_counter()
        with self._connect() as conn:
            # Cap server-side execution time where the driver supports it.
            try:
                conn.call_timeout = int(limits.max_execution_seconds * 1000)
            except Exception:  # noqa: BLE001 - not fatal if unsupported
                pass
            with conn.cursor() as cur:
                cur.execute(exec_sql, exec_binds)
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
