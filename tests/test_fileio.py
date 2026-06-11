"""B3 — atomic JSON writes (ADR-014, closes ITM-013/RISK-16).

Proves the temp+fsync+os.replace contract: a failed write leaves the target
exactly as it was and no temp file behind, and the on-disk shape matches what
``json.dump`` produced before the swap.
"""

import json
from datetime import date

import pytest

from src.core.fileio import atomic_write_json


def test_round_trip(tmp_path):
    target = tmp_path / "data.json"
    atomic_write_json(str(target), {"a": 1, "b": ["x", "y"]})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1, "b": ["x", "y"]}


def test_overwrites_existing_file(tmp_path):
    target = tmp_path / "data.json"
    atomic_write_json(str(target), {"v": 1})
    atomic_write_json(str(target), {"v": 2})
    assert json.loads(target.read_text(encoding="utf-8")) == {"v": 2}


def test_creates_parent_directories(tmp_path):
    target = tmp_path / "nested" / "deeper" / "data.json"
    atomic_write_json(str(target), {"ok": True})
    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}


def test_default_serializer_is_honoured(tmp_path):
    target = tmp_path / "data.json"
    atomic_write_json(str(target), {"d": date(2026, 6, 11)}, default=str)
    assert json.loads(target.read_text(encoding="utf-8")) == {"d": "2026-06-11"}


def test_failed_write_leaves_old_content_intact(tmp_path):
    """The torn-write scenario (ITM-013): json.dump emits partial output before
    raising, but the target must keep its previous complete content."""
    target = tmp_path / "data.json"
    atomic_write_json(str(target), {"ok": 1})

    class Unserializable:
        pass

    with pytest.raises(TypeError):
        atomic_write_json(str(target), {"good": "prefix", "bad": Unserializable()})
    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": 1}


def test_no_temp_files_left_behind(tmp_path):
    target = tmp_path / "data.json"
    atomic_write_json(str(target), {"ok": 1})

    class Unserializable:
        pass

    with pytest.raises(TypeError):
        atomic_write_json(str(target), {"bad": Unserializable()})
    assert [p.name for p in tmp_path.iterdir()] == ["data.json"]


def test_failed_first_write_leaves_no_target(tmp_path):
    target = tmp_path / "data.json"

    class Unserializable:
        pass

    with pytest.raises(TypeError):
        atomic_write_json(str(target), {"bad": Unserializable()})
    assert not target.exists()
    assert list(tmp_path.iterdir()) == []
