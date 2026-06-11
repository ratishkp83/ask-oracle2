"""Tests for retiring the legacy manual connection store (ITM-006).

The encrypted ProfileStore is the single persistence path. The manual
connection no longer writes to disk; any legacy ``connection.json`` is
imported once (session-only) and deleted — which also removes a pre-Phase-4
file that may still hold a plaintext password.
"""

import json

import src.storage as storage


def _write_legacy(cfg_file, payload):
    cfg_file.write_text(json.dumps(payload), encoding="utf-8")


def test_migrate_legacy_connection_imports_and_deletes(tmp_path, monkeypatch):
    cfg_file = tmp_path / "connection.json"
    monkeypatch.setattr(storage, "CONFIG_FILE", str(cfg_file))
    _write_legacy(
        cfg_file,
        {"host": "db.local", "port": 1521, "service_name": "XEPDB1", "username": "reporter"},
    )

    migrated = storage.migrate_legacy_connection()
    assert migrated is not None
    assert migrated["host"] == "db.local" and migrated["username"] == "reporter"
    assert not cfg_file.exists()  # the second on-disk path is retired

    # Idempotent — nothing left to migrate.
    assert storage.migrate_legacy_connection() is None


def test_migrate_removes_pre_f5_plaintext_password_file(tmp_path, monkeypatch):
    # An old (pre-Phase-4) file may have held a plaintext password; migration
    # imports it for the session and removes the at-rest secret.
    cfg_file = tmp_path / "connection.json"
    monkeypatch.setattr(storage, "CONFIG_FILE", str(cfg_file))
    _write_legacy(cfg_file, {"host": "db", "username": "u", "password": "old-plaintext"})

    migrated = storage.migrate_legacy_connection()
    assert migrated["password"] == "old-plaintext"  # available for this session only
    assert not cfg_file.exists()  # the plaintext-at-rest is gone


def test_migrate_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "CONFIG_FILE", str(tmp_path / "connection.json"))
    assert storage.migrate_legacy_connection() is None


def test_plaintext_write_path_is_removed():
    # ITM-006: the connection.json *write* path no longer exists.
    assert not hasattr(storage, "save_connection_config")
