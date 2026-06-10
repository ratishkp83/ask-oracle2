"""Central logging configuration: structured JSON to stdout, env-driven.

Idempotent — safe to call repeatedly. Streamlit re-runs the script top-to-bottom
on every interaction, so :func:`configure_logging` must not stack duplicate
handlers. Configuration is applied once per process to the ``ask_oracle`` logger
namespace (``ask_oracle.audit``, ``ask_oracle.introspection``, … inherit it).

Secret-free by policy: callers attach structured fields via
``logger.info("event", extra={"extra_fields": {...}})`` and must never include
credentials, bind values, or raw SQL — only the same fingerprint-level data the
audit module already emits.

The request-correlation id (``request_id`` / ``error_id``) lives here as a
``ContextVar`` so the formatter can stamp every record without the caller
threading it through. The HTTP middleware sets it per request; the
:mod:`src.core.errors` helpers and :mod:`src.api` import the accessors from
here. (Kept here rather than in ``errors`` to avoid an import cycle: the
formatter is the most central reader of the id.)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from contextvars import ContextVar
from typing import Optional

_LOGGER_NAMESPACE = "ask_oracle"
_CONFIGURED_ATTR = "_ask_oracle_configured"

# Per-request correlation id; ``None`` outside a request scope (e.g. the UI,
# which generates its own id at the point of failure instead).
_request_id: ContextVar[Optional[str]] = ContextVar("ask_oracle_request_id", default=None)

# Base LogRecord attributes the JSON formatter emits explicitly; anything in a
# record's ``extra_fields`` dict is merged on top (without overwriting these).
_BASE_KEYS = {"ts", "level", "logger", "msg", "request_id"}


def set_request_id(value: Optional[str]) -> None:
    """Bind a correlation id to the current context (set by the HTTP middleware)."""
    _request_id.set(value)


def get_request_id() -> Optional[str]:
    """Return the correlation id bound to the current context, if any."""
    return _request_id.get()


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log line (machine-parseable, 12-factor)."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        rid = get_request_id()
        if rid:
            payload["request_id"] = rid
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            for key, value in extra.items():
                if key not in payload:
                    payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # default=str keeps the call total-fail-safe on exotic values.
        return json.dumps(payload, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable single line for local development (``LOG_FORMAT=text``)."""

    def format(self, record: logging.LogRecord) -> str:
        rid = get_request_id()
        prefix = f"[{rid}] " if rid else ""
        base = f"{self.formatTime(record, '%H:%M:%S')} {record.levelname:<7} {record.name}: {prefix}{record.getMessage()}"
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict) and extra:
            fields = " ".join(f"{k}={v}" for k, v in extra.items())
            base = f"{base} | {fields}"
        if record.exc_info:
            base = f"{base}\n{self.formatException(record.exc_info)}"
        return base


def _build_formatter() -> logging.Formatter:
    fmt = os.getenv("LOG_FORMAT", "json").strip().lower()
    return TextFormatter() if fmt == "text" else JsonFormatter()


def configure_logging() -> logging.Logger:
    """Configure the ``ask_oracle`` logger once; return it.

    Reads ``LOG_LEVEL`` (default ``INFO``) and ``LOG_FORMAT`` (``json``|``text``,
    default ``json``). Idempotent: a second call refreshes the level/formatter
    in place but never adds a duplicate handler.
    """
    logger = logging.getLogger(_LOGGER_NAMESPACE)
    level_name = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)
    # Own our output; don't double-emit through the root logger.
    logger.propagate = False

    formatter = _build_formatter()
    if getattr(logger, _CONFIGURED_ATTR, False):
        # Already configured this process: refresh the formatter/level on the
        # existing handler(s) rather than appending a new one.
        for handler in logger.handlers:
            handler.setFormatter(formatter)
            handler.setLevel(level)
        return logger

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(level)
    logger.addHandler(handler)
    setattr(logger, _CONFIGURED_ATTR, True)
    return logger


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the configured ``ask_oracle`` namespace."""
    return logging.getLogger(f"{_LOGGER_NAMESPACE}.{name}")
