"""Offline coverage for the EBS pack validator's diff logic (scripts/ebs_pack_validate.py).

The live run needs an EBS instance (ITM-012); this proves the table/column
aggregation and gap detection with a mocked column lookup.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))

import ebs_pack_validate as v  # noqa: E402
from src.core.ebs_packs import get_pack  # noqa: E402


def _lookup_from(known):
    def lookup(table):
        return set(known.get(table.upper(), set()))
    return lookup


def test_required_columns_includes_keys_glossary_and_joins():
    req = v.required_columns(get_pack("AP"))
    assert {"INVOICE_ID", "VENDOR_ID"} <= req["AP_INVOICES_ALL"]
    # A cross-module join target (PO/AP share suppliers) is aggregated too.
    assert "AP_SUPPLIERS" in req


def test_validate_pack_all_present_is_ok():
    pack = get_pack("GL")
    known = {t: cols | {"EXTRA_COL"} for t, cols in v.required_columns(pack).items()}
    res = v.validate_pack(pack, _lookup_from(known))
    assert res.ok
    assert all(t.found and not t.missing_columns for t in res.tables)


def test_validate_pack_flags_missing_table():
    pack = get_pack("AP")
    known = dict(v.required_columns(pack))
    known.pop("AP_SUPPLIERS")  # simulate a table absent in this EBS
    res = v.validate_pack(pack, _lookup_from(known))
    assert not res.ok
    assert any(t.table == "AP_SUPPLIERS" and not t.found for t in res.tables)


def test_validate_pack_flags_missing_column():
    pack = get_pack("OM")
    known = {t: set(cols) for t, cols in v.required_columns(pack).items()}
    known["OE_ORDER_LINES_ALL"].discard("SHIPPED_QUANTITY")
    res = v.validate_pack(pack, _lookup_from(known))
    assert not res.ok
    tr = next(t for t in res.tables if t.table == "OE_ORDER_LINES_ALL")
    assert "SHIPPED_QUANTITY" in tr.missing_columns
