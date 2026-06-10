"""Tests for the saved-report store, legacy migration, and bind coercion."""

import json
from datetime import date

import pytest
from pydantic import ValidationError

from src.core.reports import (
    InMemoryReportStore,
    JsonFileReportStore,
    ReportCreate,
    ReportParam,
    coerce_report_binds,
)


def make_create(**overrides) -> ReportCreate:
    base = dict(name="AP Invoices", description="", sql="SELECT 1 FROM DUAL", parameters=[])
    base.update(overrides)
    return ReportCreate(**base)


# --- store CRUD ----------------------------------------------------------- #
def test_create_assigns_id_and_timestamps():
    store = InMemoryReportStore()
    r = store.create(make_create())
    assert r.id and r.created_at and r.updated_at
    assert r.name == "AP Invoices"


def test_duplicate_name_rejected():
    store = InMemoryReportStore()
    store.create(make_create())
    with pytest.raises(ValueError):
        store.create(make_create())


def test_update_changes_fields_and_keeps_id():
    store = InMemoryReportStore()
    r = store.create(make_create())
    updated = store.update(r.id, make_create(name="AP Invoices v2", sql="SELECT 2 FROM DUAL"))
    assert updated is not None
    assert updated.id == r.id
    assert updated.name == "AP Invoices v2"
    assert updated.created_at == r.created_at  # creation time preserved
    assert store.update("missing", make_create()) is None


def test_delete_semantics():
    store = InMemoryReportStore()
    r = store.create(make_create())
    assert store.delete(r.id) is True
    assert store.get(r.id) is None
    assert store.delete("missing") is False


# --- persistence + legacy migration --------------------------------------- #
def test_file_store_round_trips(tmp_path):
    path = tmp_path / "reports.json"
    store = JsonFileReportStore(str(path))
    r = store.create(make_create(parameters=[ReportParam(name="org_id", type="number")]))

    store2 = JsonFileReportStore(str(path))
    again = store2.get(r.id)
    assert again is not None
    assert again.parameters[0].name == "org_id"


def test_legacy_reports_json_is_migrated(tmp_path):
    path = tmp_path / "reports.json"
    # Phase-1 shape: keyed by report NAME, value is just {"sql": ...}
    legacy = {"Old Report": {"sql": "SELECT * FROM dual"}}
    path.write_text(json.dumps(legacy), encoding="utf-8")

    store = JsonFileReportStore(str(path))
    reports = store.list()
    assert len(reports) == 1
    migrated = reports[0]
    assert migrated.name == "Old Report"
    assert migrated.sql == "SELECT * FROM dual"
    assert migrated.id and migrated.parameters == []

    # The file is rewritten in v2 shape (keyed by id, with id/name fields).
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    (rid, rec), = on_disk.items()
    assert rec["id"] == rid and rec["name"] == "Old Report"


# --- parameter model validation ------------------------------------------- #
def test_bad_bind_name_rejected():
    with pytest.raises(ValidationError):
        ReportParam(name="1bad")
    with pytest.raises(ValidationError):
        ReportParam(name="drop table")


def test_label_defaults_to_name():
    p = ReportParam(name="org_id")
    assert p.label == "org_id"


# --- coerce_report_binds -------------------------------------------------- #
def test_coerce_applies_defaults_and_types():
    params = [
        ReportParam(name="org_id", type="number", default=204),
        ReportParam(name="date_from", type="date", required=False),
        ReportParam(name="status", type="string", default="OPEN"),
    ]
    binds = coerce_report_binds(params, {"date_from": "2026-01-31"})
    assert binds["org_id"] == 204
    assert binds["status"] == "OPEN"
    assert binds["date_from"] == date(2026, 1, 31)


def test_coerce_missing_required_raises():
    params = [ReportParam(name="org_id", type="number", required=True)]
    with pytest.raises(ValueError, match="Missing required"):
        coerce_report_binds(params, {})


def test_coerce_rejects_unknown_key():
    params = [ReportParam(name="org_id", type="number")]
    with pytest.raises(ValueError, match="Unknown parameter"):
        coerce_report_binds(params, {"org_id": 1, "evil": 2})


def test_coerce_number_type_validation():
    params = [ReportParam(name="amount", type="number")]
    with pytest.raises(ValueError, match="must be a number"):
        coerce_report_binds(params, {"amount": "not-a-number"})


@pytest.mark.parametrize("bad", ["nan", "inf", "-inf", "1e400"])
def test_coerce_rejects_non_finite_numbers(bad):
    # F3: "nan"/"inf"/overflow must be rejected, not coerced to float NaN/Inf.
    params = [ReportParam(name="amount", type="number")]
    with pytest.raises(ValueError, match="finite number"):
        coerce_report_binds(params, {"amount": bad})


def test_coerce_optional_without_value_is_skipped():
    params = [ReportParam(name="org_id", type="number", required=False)]
    assert coerce_report_binds(params, {}) == {}
