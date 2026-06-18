"""PostgreSQL / Supabase engine (Phase 11 — multi-engine MVP).

A second :class:`DatabaseEngine` alongside the Oracle :class:`~src.db.OracleClient`,
exposing the **same** ``run_select(sql, limits, binds) -> QueryResult`` contract so
the rest of the app (the ``/execute`` chokepoint, introspection, reports) is engine-
agnostic. Every query still passes the SELECT-only safety gate — here with the
**postgres** sqlglot dialect — and the session is opened **read-only** (defence in
depth, mirroring the Oracle read-only-account precondition, ADR-009).

``psycopg2`` is imported lazily inside :meth:`_connect` so the Oracle path never
needs the dependency and the module imports cleanly without it.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from src.core.config import SafetyLimits, load_safety_limits
from src.core.sql_safety import SqlSafetyError, assert_safe_select
from src.db import QueryResult, validate_binds, validate_schema_name

_DIALECT = "postgres"

# Oracle-style ``:name`` placeholders → psycopg2 ``%(name)s`` (pyformat). The
# lookbehind/ahead avoid Postgres ``::type`` casts and qualified ``:`` usage.
_NAMED_BIND_RE = re.compile(r"(?<![:\w]):([A-Za-z_]\w*)(?!\w)")


@dataclass
class PostgresConnectionConfig:
    host: str
    port: int
    database: str
    username: str
    password: str
    # Supabase (and most managed Postgres) require TLS.
    sslmode: str = "require"
    # Optional default schema — like Oracle current_schema; applied via SET search_path.
    search_path: Optional[str] = None


def _to_pyformat(sql: str) -> str:
    """Translate ``:name`` binds to psycopg2 ``%(name)s`` (only when binds are used)."""
    return _NAMED_BIND_RE.sub(r"%(\1)s", sql)


def _approx_row_bytes(row: Tuple[Any, ...]) -> int:
    total = 0
    for value in row:
        if value is None:
            total += 1
        else:
            try:
                total += len(str(value))
            except Exception:  # noqa: BLE001
                total += 8
    return total


class PostgresClient:
    """Read-only PostgreSQL client with the same surface as ``OracleClient``."""

    engine = "postgres"

    def __init__(self, config: PostgresConnectionConfig):
        self.config = config

    def _connect(self):
        try:
            import psycopg2  # lazy — the Oracle path never imports this
        except ImportError as exc:  # pragma: no cover - environment-dependent
            raise SqlSafetyError(
                "PostgreSQL support requires the 'psycopg2-binary' package."
            ) from exc
        conn = psycopg2.connect(
            host=self.config.host,
            port=self.config.port,
            dbname=self.config.database,
            user=self.config.username,
            password=self.config.password,
            sslmode=self.config.sslmode or "require",
            connect_timeout=10,
        )
        # Defence in depth: a read-only session refuses any write regardless of the
        # account's grants (complements the SELECT-only parse gate). Autocommit so a
        # single SELECT needs no explicit transaction management.
        conn.set_session(readonly=True, autocommit=True)
        if self.config.search_path:
            schema = validate_schema_name(self.config.search_path)
            with conn.cursor() as cur:
                cur.execute(f"SET search_path TO {schema}")
        return conn

    def run_select(
        self,
        sql: str,
        limits: Optional[SafetyLimits] = None,
        binds: Optional[Dict[str, Any]] = None,
    ) -> QueryResult:
        safety = assert_safe_select(sql, dialect=_DIALECT)
        if not safety.allowed:
            raise SqlSafetyError(safety.reason or "Only SELECT/CTE queries are allowed.")
        safe_binds = validate_binds(binds)
        limits = limits or load_safety_limits()
        # Only switch to %(name)s + a params dict when binds are actually present —
        # a bare SELECT with `%` literals (LIKE '%x%') must NOT be %-interpolated.
        exec_sql = _to_pyformat(sql) if safe_binds else sql
        exec_params = safe_binds or None

        start = time.perf_counter()
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                try:
                    cur.execute(
                        "SET statement_timeout = %s",
                        (int(limits.max_execution_seconds * 1000),),
                    )
                except Exception:  # noqa: BLE001 - non-fatal if unsupported
                    pass
                cur.execute(exec_sql, exec_params)
                columns = [d[0] for d in cur.description] if cur.description else []
                rows: List[Tuple[Any, ...]] = []
                total_bytes = 0
                truncated = False
                while True:
                    row = cur.fetchone()
                    if row is None:
                        break
                    row = tuple(row)
                    rows.append(row)
                    total_bytes += _approx_row_bytes(row)
                    if len(rows) >= limits.max_rows or total_bytes >= limits.max_result_bytes:
                        if cur.fetchone() is not None:
                            truncated = True
                        break
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        elapsed = time.perf_counter() - start
        return QueryResult(
            columns=columns,
            rows=rows,
            elapsed_seconds=elapsed,
            truncated=truncated,
            row_count=len(rows),
        )

    def test_connection(self) -> QueryResult:
        return self.run_select("SELECT 1")
