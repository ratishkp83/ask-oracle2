"""ADR-018 — per-profile default schema (ALTER SESSION SET CURRENT_SCHEMA).

Validates the injection-safe identifier check, the connect-time ALTER SESSION,
and that current_schema round-trips through the profile models/stores."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from src.core.crypto import encrypt_secret
from src.core.profiles import InMemoryProfileStore, JsonFileProfileStore, ProfileCreate
from src.core.sql_safety import SqlSafetyError
from src.db import OracleClient, OracleConnectionConfig, validate_schema_name


def _cfg(**over) -> OracleConnectionConfig:
    base = dict(host="h", port=1521, service_name="s", sid=None,
                username="u", password="p", current_schema=None)
    base.update(over)
    return OracleConnectionConfig(**base)


# --- identifier validation (injection control) --------------------------- #
@pytest.mark.parametrize("good", ["AOR_DEMO", "hr", "C##ADMIN", "x$y", "A1_B2"])
def test_validate_schema_name_ok(good):
    assert validate_schema_name(good) == good


@pytest.mark.parametrize("bad", ["", "   ", "1abc", "a b", "a;b", "a'b", "a-b", "a.b",
                                 '"x"', "a)b", "AOR_DEMO; DROP TABLE t", "a" * 129])
def test_validate_schema_name_rejects(bad):
    with pytest.raises(SqlSafetyError):
        validate_schema_name(bad)


# --- connect-time ALTER SESSION ------------------------------------------ #
def test_connect_sets_current_schema():
    with patch("oracledb.connect") as mock_connect:
        conn, cur = MagicMock(), MagicMock()
        conn.cursor.return_value.__enter__.return_value = cur
        mock_connect.return_value = conn
        OracleClient(_cfg(current_schema="AOR_DEMO"))._connect()
        cur.execute.assert_called_once_with("ALTER SESSION SET CURRENT_SCHEMA = AOR_DEMO")


def test_connect_without_schema_runs_no_alter():
    with patch("oracledb.connect") as mock_connect:
        conn = MagicMock()
        mock_connect.return_value = conn
        OracleClient(_cfg(current_schema=None))._connect()
        conn.cursor.assert_not_called()


def test_connect_rejects_injection_in_schema():
    with patch("oracledb.connect") as mock_connect:
        mock_connect.return_value = MagicMock()
        with pytest.raises(SqlSafetyError):
            OracleClient(_cfg(current_schema="AOR_DEMO; DROP TABLE x"))._connect()


# --- profile round-trip --------------------------------------------------- #
def test_profile_current_schema_roundtrip():
    store = InMemoryProfileStore()
    pub = store.create(ProfileCreate(name="x", host="h", service_name="s",
                                     username="u", password="p", current_schema="AOR_DEMO"))
    assert pub.current_schema == "AOR_DEMO"
    assert store.get(pub.id).current_schema == "AOR_DEMO"
    assert store.resolve(pub.id).current_schema == "AOR_DEMO"


def test_profile_default_schema_is_none():
    store = InMemoryProfileStore()
    pub = store.create(ProfileCreate(name="y", host="h", service_name="s",
                                     username="u", password="p"))
    assert pub.current_schema is None
    assert store.resolve(pub.id).current_schema is None


def test_legacy_profile_record_loads_without_current_schema(tmp_path):
    # A pre-ADR-018 record (no current_schema key) must still load → None.
    path = tmp_path / "profiles.json"
    rec = {
        "id": "abc", "name": "Legacy", "host": "h", "port": 1521,
        "service_name": "s", "sid": None, "username": "u", "environment": "DEV",
        "password_encrypted": encrypt_secret("pw"),
    }
    path.write_text(json.dumps({"abc": rec}))
    store = JsonFileProfileStore(path=str(path))
    pub = store.get("abc")
    assert pub is not None and pub.current_schema is None
    assert store.resolve("abc").current_schema is None
