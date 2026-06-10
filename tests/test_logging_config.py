"""B1 — structured logging config + JSON audit emission.

No network, no Oracle. Exercises the formatter, idempotency, env knobs, and that
the audit record now emits valid, secret-free JSON.
"""

import json
import logging

import pytest

from src.core import audit
from src.core.logging_config import (
    JsonFormatter,
    TextFormatter,
    configure_logging,
    get_request_id,
    set_request_id,
)


class _Capture(logging.Handler):
    """Collect formatted log lines for assertions."""

    def __init__(self, formatter: logging.Formatter):
        super().__init__()
        self.setFormatter(formatter)
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


@pytest.fixture
def reset_request_id():
    yield
    set_request_id(None)


def _make_record(msg: str = "hello", **extra) -> logging.LogRecord:
    record = logging.LogRecord("ask_oracle.test", logging.INFO, __file__, 1, msg, None, None)
    if extra:
        record.extra_fields = extra
    return record


def test_json_formatter_emits_valid_json_with_base_keys():
    line = JsonFormatter().format(_make_record("an_event", foo="bar", n=3))
    payload = json.loads(line)  # raises if not valid JSON
    assert payload["level"] == "INFO"
    assert payload["logger"] == "ask_oracle.test"
    assert payload["msg"] == "an_event"
    assert payload["foo"] == "bar" and payload["n"] == 3
    assert "ts" in payload


def test_json_formatter_stamps_request_id(reset_request_id):
    set_request_id("req-123")
    payload = json.loads(JsonFormatter().format(_make_record()))
    assert payload["request_id"] == "req-123"


def test_json_formatter_omits_request_id_when_unset(reset_request_id):
    set_request_id(None)
    payload = json.loads(JsonFormatter().format(_make_record()))
    assert "request_id" not in payload


def test_text_formatter_is_human_readable_not_json():
    line = TextFormatter().format(_make_record("an_event", action="create"))
    assert "an_event" in line
    assert "action=create" in line
    with pytest.raises(json.JSONDecodeError):
        json.loads(line)


def test_configure_logging_is_idempotent():
    configure_logging()
    logger = logging.getLogger("ask_oracle")
    count = len(logger.handlers)
    configure_logging()
    configure_logging()
    assert len(logger.handlers) == count  # no duplicate handlers stacked
    assert count >= 1


def test_log_level_env_is_respected(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "WARNING")
    configure_logging()
    assert logging.getLogger("ask_oracle").level == logging.WARNING
    # Restore default for the rest of the suite.
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    configure_logging()
    assert logging.getLogger("ask_oracle").level == logging.INFO


def test_audit_execution_emits_valid_json_without_secrets():
    logger = logging.getLogger("ask_oracle")
    cap = _Capture(JsonFormatter())
    logger.addHandler(cap)
    try:
        audit.audit_execution(
            source="api",
            sql="SELECT * FROM emp WHERE ssn = '123-45-6789'",
            allowed=True,
            profile_id="p1",
            username="scott",
            row_count=5,
            elapsed_seconds=0.123,
        )
    finally:
        logger.removeHandler(cap)

    assert cap.lines, "audit produced no log line"
    payload = json.loads(cap.lines[-1])  # valid JSON
    assert payload["event"] == "sql_execute"
    assert payload["sql_sha256"]  # fingerprint present
    # Secret-free: neither the raw SQL literal nor a password leaks.
    raw = cap.lines[-1]
    assert "123-45-6789" not in raw
    assert "ssn" not in raw.lower()
    assert "password" not in raw.lower()
