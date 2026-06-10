"""Redaction tests — external prompts must carry schema names only, no values."""

import pytest

from src.core.llm.redaction import RedactionError, assert_no_values, build_external_context
from src.schema import ColumnDefinition, Schema, TableDefinition


def _schema() -> Schema:
    s = Schema()
    s.tables["EMP"] = TableDefinition(
        name="EMP",
        columns=[
            ColumnDefinition(table_name="EMP", column_name="EMP_ID", data_type="NUMBER", is_primary_key=True),
            ColumnDefinition(table_name="EMP", column_name="SALARY", data_type="NUMBER"),
        ],
    )
    return s


def test_external_context_has_names_not_values():
    ctx = build_external_context(_schema())
    assert "EMP" in ctx and "SALARY" in ctx
    assert_no_values(ctx)  # clean schema context must not raise


def test_assert_no_values_rejects_data_markers():
    with pytest.raises(RedactionError):
        assert_no_values("Schema:\n- EMP\nSample values: 1000, 2000, 3000")
