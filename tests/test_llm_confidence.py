"""Confidence heuristic tests."""

from src.core.llm.confidence import assess_confidence
from src.schema import ColumnDefinition, Schema, TableDefinition


def _schema() -> Schema:
    s = Schema()
    s.tables["EMP"] = TableDefinition(
        name="EMP",
        columns=[
            ColumnDefinition(table_name="EMP", column_name="EMP_ID"),
            ColumnDefinition(table_name="EMP", column_name="SALARY"),
            ColumnDefinition(table_name="EMP", column_name="DEPT_ID"),
        ],
    )
    return s


def test_high_when_all_identifiers_resolve():
    c = assess_confidence("SELECT emp_id, salary FROM emp", _schema())
    assert c.level == "High"


def test_low_when_unknown_table():
    c = assess_confidence("SELECT x FROM bogus_table", _schema())
    assert c.level == "Low"


def test_medium_when_only_unknown_column():
    c = assess_confidence("SELECT not_a_col FROM emp", _schema())
    assert c.level == "Medium"
    assert any("not_a_col" in r.lower() for r in c.reasons)


def test_low_when_no_schema():
    c = assess_confidence("SELECT 1 FROM dual", Schema())
    assert c.level == "Low"
