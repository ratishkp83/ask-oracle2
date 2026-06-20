"""Engine factory (Phase 11 — multi-engine MVP).

Returns the right read-only client for a connection config: ``PostgresClient`` for a
:class:`~src.core.db_postgres.PostgresConnectionConfig`, else the Oracle
:class:`~src.db.OracleClient` (the default). Both expose the same
``run_select(sql, limits, binds) -> QueryResult`` contract, so callers stay
engine-agnostic.
"""
from __future__ import annotations

from typing import Any

from src.core.db_postgres import PostgresClient, PostgresConnectionConfig
from src.db import OracleClient

# Engine discriminator values used by profiles / connection payloads.
ENGINE_ORACLE = "oracle"
ENGINE_POSTGRES = "postgres"
SUPPORTED_ENGINES = (ENGINE_ORACLE, ENGINE_POSTGRES)


def make_client(config: Any):
    """Build a read-only DB client for ``config`` based on its type."""
    if isinstance(config, PostgresConnectionConfig):
        return PostgresClient(config)
    return OracleClient(config)
