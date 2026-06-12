"""B1 — EBS metadata packs integrity + redaction-safety (Phase 7, ADR-015).

Packs are curated metadata (names/descriptions only). These tests prove the
packs are internally consistent, describe the tables the template catalog
already uses, and that the prompt context they generate can never trip the
external-prompt data tripwire.
"""

import re

import pytest

from src.core.ebs_packs import build_ebs_context, get_pack, list_packs
from src.core.llm.redaction import _FORBIDDEN_MARKERS, assert_no_values
from src.core.templates import list_templates

MODULES = {"GL", "AP", "AR", "PO", "OM"}
_JOIN_RE = re.compile(r"^[A-Z0-9_]+\.[a-z0-9_]+ -> [A-Z0-9_]+\.[a-z0-9_]+$")


def _all_tables() -> set:
    return {t.table for p in list_packs() for t in p.tables}


def test_all_five_modules_present_and_populated():
    packs = list_packs()
    assert {p.module for p in packs} == MODULES
    for p in packs:
        assert p.tables, f"{p.module} has no tables"
        assert p.glossary, f"{p.module} has no glossary"


def test_glossary_terms_reference_real_pack_tables():
    tables = _all_tables()
    for p in list_packs():
        for g in p.glossary:
            assert g.table in tables, f"{p.module} glossary '{g.term}' → unknown table {g.table}"


def test_join_hints_are_well_formed_and_reference_real_tables():
    tables = _all_tables()
    for p in list_packs():
        for t in p.tables:
            for j in t.joins:
                assert _JOIN_RE.match(j), f"malformed join on {t.table}: {j!r}"
                left, right = j.split(" -> ")
                assert left.split(".")[0] in tables and right.split(".")[0] in tables
                assert t.table in j, f"join on {t.table} doesn't reference it: {j!r}"


def test_packs_describe_the_tables_the_templates_use():
    # Consistency with the Phase-4 template catalog: every table a template
    # SELECTs/JOINs must be described by a pack.
    described = _all_tables()
    referenced = set()
    for tmpl in list_templates():
        for m in re.finditer(r"\b(?:FROM|JOIN)\s+([A-Za-z0-9_]+)", tmpl.sql, re.IGNORECASE):
            referenced.add(m.group(1).upper())
    missing = referenced - described
    assert not missing, f"templates use tables not in any pack: {sorted(missing)}"


def test_get_pack_case_insensitive_and_unknown():
    assert get_pack("ap").module == "AP"
    assert get_pack("Gl").module == "GL"
    assert get_pack("XX") is None
    assert get_pack("") is None


def test_context_is_metadata_only_and_passes_tripwire():
    context = build_ebs_context(sorted(MODULES))
    assert context
    lower = context.lower()
    for marker in _FORBIDDEN_MARKERS:
        assert marker not in lower, f"context contains forbidden data marker {marker!r}"
    # The actual guard used in the NL→SQL path must not raise on pack context.
    assert_no_values(context)


def test_context_empty_when_no_modules_selected():
    assert build_ebs_context([]) == ""
    assert build_ebs_context(None) == ""  # type: ignore[arg-type]


def test_context_scopes_to_selected_modules():
    gl = build_ebs_context(["GL"])
    assert "GL_BALANCES" in gl
    assert "AP_INVOICES_ALL" not in gl
    # Case-insensitive selection.
    assert build_ebs_context(["gl"]) == gl


def test_context_includes_glossary_mappings():
    ap = build_ebs_context(["AP"])
    assert "invoice -> AP_INVOICES_ALL" in ap
    assert "supplier -> AP_SUPPLIERS" in ap
