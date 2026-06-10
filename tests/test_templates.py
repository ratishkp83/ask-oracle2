"""Tests for the curated EBS template catalog (Phase 4).

The key safety property: every shipped template must be a provably safe SELECT,
and its declared parameters must exactly match the `:binds` used in its SQL.
"""

import re

from fastapi.testclient import TestClient

from src.api import app
from src.core.sql_safety import assert_safe_select
from src.core.templates import get_template, list_templates

client = TestClient(app)

_BIND_RE = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")


def test_catalog_covers_all_modules():
    templates = list_templates()
    assert len(templates) >= 10
    modules = {t.module for t in templates}
    assert modules == {"GL", "AP", "AR", "PO", "OM"}


def test_every_template_is_a_safe_select():
    for t in list_templates():
        result = assert_safe_select(t.sql)
        assert result.allowed, f"{t.id} is not a safe SELECT: {result.reason}"


def test_template_params_match_binds():
    for t in list_templates():
        declared = {p.name for p in t.parameters}
        used = set(_BIND_RE.findall(t.sql))
        assert declared == used, f"{t.id}: declared {declared} != used {used}"


def test_template_ids_unique():
    ids = [t.id for t in list_templates()]
    assert len(ids) == len(set(ids))


def test_get_template_lookup():
    first = list_templates()[0]
    assert get_template(first.id).id == first.id
    assert get_template("does-not-exist") is None


# --- API ------------------------------------------------------------------ #
def test_templates_endpoint_lists_catalog():
    resp = client.get("/templates")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == len(list_templates())
    assert {"id", "module", "name", "description", "sql", "parameters"} <= set(body[0])


def test_template_by_id_endpoint():
    tid = list_templates()[0].id
    assert client.get(f"/templates/{tid}").status_code == 200
    assert client.get("/templates/nope").status_code == 404
