"""NL->SQL output cleanup: strip the trailing statement terminator (ORA-00933)
and steer the prompt to Oracle row-limiting dialect."""

from __future__ import annotations

import pytest

from src.nl2sql import SYSTEM_PROMPT, _parse_sql_and_explanation


@pytest.mark.parametrize("raw,expected", [
    ("```sql\nSELECT a FROM t;\n```", "SELECT a FROM t"),
    ("```sql\nSELECT a FROM t ;  \n```", "SELECT a FROM t"),
    ("SELECT a FROM t;;", "SELECT a FROM t"),
    ("SELECT a FROM t", "SELECT a FROM t"),  # nothing to strip
])
def test_strips_trailing_terminator(raw, expected):
    sql, _, _ = _parse_sql_and_explanation(raw)
    assert sql == expected


def test_keeps_semicolon_inside_string_literal():
    sql, _, _ = _parse_sql_and_explanation("```sql\nSELECT a FROM t WHERE x = 'a;b'\n```")
    assert sql == "SELECT a FROM t WHERE x = 'a;b'"


def test_strips_terminator_before_explanation():
    sql, expl, _ = _parse_sql_and_explanation(
        "```sql\nSELECT a FROM t FETCH FIRST 5 ROWS ONLY;\n```\nExplanation: top 5 rows."
    )
    assert sql == "SELECT a FROM t FETCH FIRST 5 ROWS ONLY"
    assert expl == "top 5 rows."


def test_parses_interpreted_question():
    sql, expl, interp = _parse_sql_and_explanation(
        "```sql\nSELECT first_name, salary FROM employees ORDER BY salary DESC FETCH FIRST 1 ROW ONLY\n```\n"
        "Interpreted question: Who is the highest-paid employee?\n"
        "Explanation: returns the employee with the maximum salary."
    )
    assert sql.startswith("SELECT first_name")
    assert interp == "Who is the highest-paid employee?"
    assert expl == "returns the employee with the maximum salary."


def test_prompt_steers_oracle_dialect():
    # The system prompt must forbid LIMIT and the trailing semicolon.
    assert "FETCH FIRST" in SYSTEM_PROMPT
    assert "never LIMIT" in SYSTEM_PROMPT
    assert "semicolon" in SYSTEM_PROMPT.lower()
