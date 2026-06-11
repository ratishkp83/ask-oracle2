"""B4 — corrupt-record quarantine in the JSON stores (ADR-014, closes ITM-014).

A malformed record used to raise an uncaught ValidationError out of
``_deserialize``/``_load`` (→ 500 on list/get). Now it is quarantined: not
served, logged once with a reference id, and **preserved verbatim on save** so
a later write cannot silently drop it.
"""

import json
import logging

import pytest

from src.core.logging_config import JsonFormatter
from src.core.profiles import JsonFileProfileStore, ProfileCreate
from src.core.reports import JsonFileReportStore, ReportCreate
from src.core.schema_store import JsonFileSchemaStore


class _Capture(logging.Handler):
    def __init__(self):
        super().__init__()
        self.setFormatter(JsonFormatter())
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


@pytest.fixture
def server_logs():
    logger = logging.getLogger("ask_oracle")
    cap = _Capture()
    logger.addHandler(cap)
    try:
        yield cap
    finally:
        logger.removeHandler(cap)


def _inject(path, key, record):
    raw = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    raw[key] = record
    path.write_text(json.dumps(raw), encoding="utf-8")


# --------------------------------------------------------------------------- #
# Report store
# --------------------------------------------------------------------------- #
CORRUPT_V2 = {"id": "bad-1", "name": "Bad", "sql": "SELECT 1", "parameters": "not-a-list"}


def test_corrupt_v2_report_is_skipped_not_500(tmp_path, server_logs):
    path = tmp_path / "reports.json"
    store = JsonFileReportStore(str(path))
    good = store.create(ReportCreate(name="Good", sql="SELECT 1 FROM DUAL"))
    _inject(path, "bad-1", CORRUPT_V2)

    fresh = JsonFileReportStore(str(path))
    names = [r.name for r in fresh.list()]  # must not raise
    assert names == ["Good"]
    assert fresh.get(good.id) is not None
    assert fresh.get("bad-1") is None  # quarantined ids behave as not-found
    joined = "\n".join(server_logs.lines)
    assert "quarantined" in joined and "bad-1" in joined
    assert "error_id" in joined


def test_quarantined_report_survives_subsequent_saves(tmp_path):
    path = tmp_path / "reports.json"
    store = JsonFileReportStore(str(path))
    store.create(ReportCreate(name="Good", sql="SELECT 1 FROM DUAL"))
    _inject(path, "bad-1", CORRUPT_V2)

    fresh = JsonFileReportStore(str(path))
    fresh.list()  # load → quarantine
    fresh.create(ReportCreate(name="Another", sql="SELECT 2 FROM DUAL"))  # save

    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["bad-1"] == CORRUPT_V2  # preserved verbatim, not dropped
    assert len(on_disk) == 3  # 2 good + 1 quarantined


def test_corrupt_legacy_report_is_quarantined_and_survives_migration(tmp_path):
    path = tmp_path / "reports.json"
    # Legacy shape: {name: {sql}}. One migratable record, one whose sql is junk.
    path.write_text(
        json.dumps({"old-report": {"sql": "SELECT 1"}, "junk": {"sql": {"nested": 1}}}),
        encoding="utf-8",
    )
    store = JsonFileReportStore(str(path))
    names = [r.name for r in store.list()]  # triggers in-place migration save
    assert names == ["old-report"]

    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["junk"] == {"sql": {"nested": 1}}  # quarantined through the migration save
    migrated = [rec for key, rec in on_disk.items() if key != "junk"]
    assert len(migrated) == 1 and migrated[0]["name"] == "old-report"


# --------------------------------------------------------------------------- #
# Profile store
# --------------------------------------------------------------------------- #
def test_corrupt_profile_is_skipped_and_preserved(tmp_path, server_logs):
    path = tmp_path / "profiles.json"
    store = JsonFileProfileStore(str(path))
    store.create(
        ProfileCreate(name="P", host="db", service_name="XE", username="u", password="p")
    )
    _inject(path, "bad-p", {"id": "bad-p"})  # missing required fields

    fresh = JsonFileProfileStore(str(path))
    assert [p.name for p in fresh.list()] == ["P"]  # must not raise
    fresh.create(
        ProfileCreate(name="Q", host="db2", service_name="XE", username="u", password="p")
    )
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["bad-p"] == {"id": "bad-p"}
    assert "quarantined" in "\n".join(server_logs.lines)


# --------------------------------------------------------------------------- #
# Schema store
# --------------------------------------------------------------------------- #
def test_corrupt_schema_record_is_skipped_and_preserved(tmp_path, server_logs):
    path = tmp_path / "schemas.json"
    store = JsonFileSchemaStore(str(path))
    store.create("HR snapshot", {"tables": {}})
    _inject(path, "bad-s", {"id": "bad-s"})  # missing required fields

    fresh = JsonFileSchemaStore(str(path))
    assert [s.name for s in fresh.list()] == ["HR snapshot"]  # must not raise
    fresh.create("Second", {"tables": {}})
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["bad-s"] == {"id": "bad-s"}
    assert "quarantined" in "\n".join(server_logs.lines)


def test_corrupt_record_logged_once_per_instance(tmp_path, server_logs):
    path = tmp_path / "reports.json"
    store = JsonFileReportStore(str(path))
    store.create(ReportCreate(name="Good", sql="SELECT 1 FROM DUAL"))
    _inject(path, "bad-1", CORRUPT_V2)

    fresh = JsonFileReportStore(str(path))
    fresh.list()
    first = sum("quarantined" in line for line in server_logs.lines)
    fresh.list()  # second load of the same instance must not re-log
    second = sum("quarantined" in line for line in server_logs.lines)
    assert first == 1 and second == 1
