"""Unit tests for the central SQL safety layer (src/core/sql_safety.py)."""

import pytest

from src.core.sql_safety import assert_safe_select, is_safe_select

ALLOWED = [
    "SELECT 1 FROM DUAL",
    "select * from emp",
    "SELECT\n  employee_id,\n  salary\nFROM employees",  # newline after SELECT (old check failed this)
    "WITH t AS (SELECT id FROM emp) SELECT * FROM t",       # CTE
    "(SELECT id FROM emp)",                                  # parenthesised
    "SELECT a FROM t1 UNION SELECT a FROM t2",               # set operation
    "SELECT 1 FROM dual;",                                   # trailing semicolon
    "SELECT * FROM (SELECT id FROM emp) x",                  # subquery
    "SELECT id FROM emp WHERE status = 'DELETE'",            # DML keyword only in a literal
    "SELECT update_date, created_date FROM emp",             # column names contain keywords
]

REJECTED = [
    "",
    "   ",
    "INSERT INTO emp (id) VALUES (1)",
    "UPDATE emp SET salary = 0",
    "DELETE FROM emp",
    "DROP TABLE emp",
    "TRUNCATE TABLE emp",
    "ALTER TABLE emp ADD (note VARCHAR2(10))",
    "CREATE TABLE x (id NUMBER)",
    "MERGE INTO emp d USING src s ON (d.id = s.id) WHEN MATCHED THEN UPDATE SET d.x = s.x",
    "GRANT SELECT ON emp TO bob",
    "BEGIN NULL; END;",                       # PL/SQL block
    "SELECT * FROM emp; DROP TABLE emp",       # stacked statements
    "SELECT * FROM emp FOR UPDATE",            # row locking
]


@pytest.mark.parametrize("sql", ALLOWED)
def test_allowed_queries(sql):
    result = assert_safe_select(sql)
    assert result.allowed, f"expected allowed: {sql!r} -> {result.reason}"
    assert is_safe_select(sql) is True


@pytest.mark.parametrize("sql", REJECTED)
def test_rejected_queries(sql):
    result = assert_safe_select(sql)
    assert not result.allowed, f"expected rejected: {sql!r}"
    assert result.reason  # a human-readable reason is always provided
    assert is_safe_select(sql) is False
