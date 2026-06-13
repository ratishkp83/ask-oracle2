"""B1 — email config + opt-in gating (Phase 8)."""

from __future__ import annotations

import pytest

from src.core.mailer.config import (
    DEFAULT_HOST,
    DEFAULT_MAX_ATTACHMENT_MB,
    DEFAULT_PORT,
    email_enabled,
    load_config,
)

_ENV_KEYS = (
    "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD",
    "EMAIL_FROM", "EMAIL_ALLOWED_DOMAINS", "EMAIL_MAX_ATTACHMENT_MB",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_disabled_by_default():
    assert email_enabled() is False


def test_disabled_with_only_user(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "a@b.com")
    assert email_enabled() is False


def test_disabled_with_only_password(monkeypatch):
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    assert email_enabled() is False


def test_enabled_when_both_set(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "a@b.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    assert email_enabled() is True


def test_blank_user_is_disabled(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "   ")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    assert email_enabled() is False


def test_defaults(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "me@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    cfg = load_config()
    assert cfg.host == DEFAULT_HOST
    assert cfg.port == DEFAULT_PORT
    assert cfg.sender == "me@example.com"  # EMAIL_FROM defaults to SMTP_USER
    assert cfg.allowed_domains == frozenset()
    assert cfg.max_attachment_bytes == DEFAULT_MAX_ATTACHMENT_MB * 1024 * 1024


def test_password_spaces_stripped(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "me@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "abcd efgh ijkl mnop")
    assert load_config().password == "abcdefghijklmnop"


def test_email_from_override(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "login@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    monkeypatch.setenv("EMAIL_FROM", "Reports <reports@example.com>")
    assert load_config().sender == "Reports <reports@example.com>"


def test_allowed_domains_parsing(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "me@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    monkeypatch.setenv("EMAIL_ALLOWED_DOMAINS", " Example.com, @corp.io ; foo.org ")
    assert load_config().allowed_domains == frozenset({"example.com", "corp.io", "foo.org"})


@pytest.mark.parametrize("raw,expected_mb", [("5", 5), ("0", DEFAULT_MAX_ATTACHMENT_MB),
                                             ("-3", DEFAULT_MAX_ATTACHMENT_MB),
                                             ("notanumber", DEFAULT_MAX_ATTACHMENT_MB)])
def test_max_mb_parsing(monkeypatch, raw, expected_mb):
    monkeypatch.setenv("SMTP_USER", "me@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    monkeypatch.setenv("EMAIL_MAX_ATTACHMENT_MB", raw)
    assert load_config().max_attachment_bytes == expected_mb * 1024 * 1024


def test_bad_port_falls_back(monkeypatch):
    monkeypatch.setenv("SMTP_USER", "me@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "pw")
    monkeypatch.setenv("SMTP_PORT", "not-a-port")
    assert load_config().port == DEFAULT_PORT
