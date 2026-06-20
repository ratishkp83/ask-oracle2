"""Phase 11 — F2: decline a query that references a fabricated (non-schema) column
instead of running it and surfacing a raw ORA-00904. Fail-open on anything unclear."""
from __future__ import annotations

from src.nl2sql import _unknown_columns
from src.schema import schema_from_dict

SCHEMA = schema_from_dict(
    {
        "tables": {
            "EMPLOYEES": [
                {"column_name": "EMPLOYEE_ID"},
                {"column_name": "FIRST_NAME"},
                {"column_name": "SALARY"},
                {"column_name": "DEPARTMENT_ID"},
            ],
            "DEPARTMENTS": [
                {"column_name": "DEPARTMENT_ID"},
                {"column_name": "DEPARTMENT_NAME"},
            ],
        }
    }
)


def test_valid_columns_are_not_flagged():
    assert _unknown_columns("SELECT first_name, salary FROM employees", SCHEMA) == []


def test_qualified_join_columns_are_not_flagged():
    sql = (
        "SELECT e.first_name, d.department_name FROM employees e "
        "JOIN departments d ON e.department_id = d.department_id"
    )
    assert _unknown_columns(sql, SCHEMA) == []


def test_fabricated_column_is_flagged():
    sql = "SELECT first_name FROM employees WHERE hire_date >= DATE '2020-01-01'"
    flagged = [c.upper() for c in _unknown_columns(sql, SCHEMA)]
    assert "HIRE_DATE" in flagged


def test_select_aliases_are_not_flagged():
    sql = (
        "SELECT department_id, SUM(salary) AS total_pay FROM employees "
        "GROUP BY department_id ORDER BY total_pay"
    )
    assert _unknown_columns(sql, SCHEMA) == []


def test_pseudo_columns_are_not_flagged():
    assert _unknown_columns("SELECT first_name FROM employees WHERE rownum <= 5", SCHEMA) == []


def test_cte_and_window_aliases_are_not_flagged():
    sql = (
        "WITH ranked AS (SELECT first_name, salary, "
        "ROW_NUMBER() OVER (PARTITION BY department_id ORDER BY salary DESC) rn "
        "FROM employees) SELECT first_name, salary FROM ranked WHERE rn = 1"
    )
    assert _unknown_columns(sql, SCHEMA) == []


def test_fail_open_on_empty_schema():
    empty = schema_from_dict({"tables": {}})
    assert _unknown_columns("SELECT whatever FROM t", empty) == []


def test_fail_open_on_unparseable_sql():
    assert _unknown_columns("this is not sql ((", SCHEMA) == []
