"""Confidence heuristic tests (incl. join + per-table column resolution: F1, F5)."""

from src.core.llm.confidence import assess_confidence
from src.schema import ColumnDefinition, RelationshipDefinition, Schema, TableDefinition


def _emp_only() -> Schema:
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


def _emp_dept(with_rel: bool = False) -> Schema:
    s = _emp_only()
    s.tables["DEPT"] = TableDefinition(
        name="DEPT",
        columns=[
            ColumnDefinition(table_name="DEPT", column_name="DEPT_ID"),
            ColumnDefinition(table_name="DEPT", column_name="DNAME"),
        ],
    )
    if with_rel:
        s.relationships = [
            RelationshipDefinition(from_table="EMP", from_column="DEPT_ID", to_table="DEPT", to_column="DEPT_ID")
        ]
    return s


def test_high_when_all_identifiers_resolve():
    assert assess_confidence("SELECT emp_id, salary FROM emp", _emp_only()).level == "High"


def test_low_when_unknown_table():
    assert assess_confidence("SELECT x FROM bogus_table", _emp_only()).level == "Low"


def test_medium_when_only_unknown_column():
    c = assess_confidence("SELECT not_a_col FROM emp", _emp_only())
    assert c.level == "Medium"
    assert any("not_a_col" in r.lower() for r in c.reasons)


def test_low_when_no_schema():
    assert assess_confidence("SELECT 1 FROM dual", Schema()).level == "Low"


# F5 — column must resolve against its own table, not the whole schema.
def test_wrong_table_column_is_not_high():
    c = assess_confidence("SELECT dname, salary FROM dept", _emp_dept())
    assert c.level == "Medium"
    assert any("salary" in r.lower() for r in c.reasons)


# F1 — joins must be backed by a known relationship.
def test_bad_join_without_relationships_is_capped_medium():
    sql = "SELECT e.salary, d.dname FROM emp e JOIN dept d ON e.salary = d.dept_id"
    assert assess_confidence(sql, _emp_dept(with_rel=False)).level == "Medium"


def test_bad_join_with_relationships_is_low():
    sql = "SELECT e.salary, d.dname FROM emp e JOIN dept d ON e.salary = d.dept_id"
    c = assess_confidence(sql, _emp_dept(with_rel=True))
    assert c.level == "Low"
    assert any("relationship" in r.lower() for r in c.reasons)


def test_good_join_with_relationships_is_high():
    sql = "SELECT e.salary, d.dname FROM emp e JOIN dept d ON e.dept_id = d.dept_id"
    assert assess_confidence(sql, _emp_dept(with_rel=True)).level == "High"
