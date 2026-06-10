"""Tests for the legacy manual connection store (F5 — no plaintext secret at rest)."""

import json

import src.storage as storage


def test_save_connection_config_never_persists_password(tmp_path, monkeypatch):
    cfg_file = tmp_path / "connection.json"
    monkeypatch.setattr(storage, "CONFIG_FILE", str(cfg_file))

    storage.save_connection_config(
        {
            "host": "db.local",
            "port": 1521,
            "service_name": "XEPDB1",
            "sid": None,
            "username": "reporter",
            "password": "manual-secret-pw",  # must NOT reach disk (F5)
        }
    )

    raw = cfg_file.read_text(encoding="utf-8")
    assert "manual-secret-pw" not in raw
    on_disk = json.loads(raw)
    assert "password" not in on_disk
    # Non-secret fields are still persisted.
    assert on_disk["host"] == "db.local" and on_disk["username"] == "reporter"

    # Round-trips without a password field.
    loaded = storage.load_connection_config()
    assert loaded is not None and "password" not in loaded
