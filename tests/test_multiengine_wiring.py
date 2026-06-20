"""Phase 11 multi-engine MVP — wiring: dialect prompt, Postgres profiles, validation."""
from __future__ import annotations

import pytest

from src.api import ConnectionConfig
from src.core.profiles import InMemoryProfileStore, ProfileCreate
from src.nl2sql import SYSTEM_PROMPT, _unknown_columns, system_prompt_for
from src.schema import schema_from_dict


def test_prompt_is_dialect_specific():
    pg = system_prompt_for("postgres")
    assert "PostgreSQL" in pg and "LIMIT n" in pg and "FETCH FIRST" not in pg
    assert system_prompt_for("oracle") == SYSTEM_PROMPT
    assert "FETCH FIRST" in SYSTEM_PROMPT  # Oracle default unchanged


def test_postgres_profile_roundtrip_carries_engine_and_database():
    store = InMemoryProfileStore()
    pub = store.create(ProfileCreate(
        name="Supabase", engine="postgres", host="db.x.supabase.co", port=5432,
        database="postgres", username="ro", password="pw", sslmode="require",
        current_schema="public",
    ))
    assert pub.engine == "postgres" and pub.database == "postgres"
    r = store.resolve(pub.id)
    assert r.engine == "postgres" and r.database == "postgres"
    assert r.sslmode == "require" and r.current_schema == "public"


def test_oracle_profile_still_defaults_engine():
    store = InMemoryProfileStore()
    pub = store.create(ProfileCreate(
        name="XE", host="h", port=1521, service_name="XE", username="u", password="p",
    ))
    assert pub.engine == "oracle"


def test_postgres_connection_requires_database():
    with pytest.raises(Exception):
        ConnectionConfig(engine="postgres", host="h", port=5432, username="u", password="p")
    # With a database it validates.
    ok = ConnectionConfig(engine="postgres", host="h", port=5432, database="postgres",
                          username="u", password="p")
    assert ok.engine == "postgres"


def test_unknown_columns_works_in_postgres_dialect():
    schema = schema_from_dict({"tables": {"employees": [
        {"column_name": "first_name"}, {"column_name": "salary"}]}})
    assert _unknown_columns("SELECT first_name, salary FROM employees LIMIT 5", schema, "postgres") == []
    flagged = [c.upper() for c in _unknown_columns(
        "SELECT hire_date FROM employees LIMIT 5", schema, "postgres")]
    assert "HIRE_DATE" in flagged
