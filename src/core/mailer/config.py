"""Email (SMTP) configuration — env-only, opt-in (Phase 8).

The feature is **inert unless ``SMTP_USER`` and ``SMTP_PASSWORD`` are both set**
(:func:`email_enabled`). The password lives only in this process's environment
and is never logged or returned by anything. For Gmail, ``SMTP_PASSWORD`` is an
**App Password** (the account needs 2-Step Verification); Gmail prints it in
four space-separated groups, so we tolerate spaces.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import FrozenSet, Optional

DEFAULT_HOST = "smtp.gmail.com"
DEFAULT_PORT = 587
# 17 MB *raw* keeps the base64-encoded message under Gmail's 25 MB limit
# (base64 inflates the attachment by ~33%; P8-R1-F1). Raise only if the
# provider's message-size limit is higher.
DEFAULT_MAX_ATTACHMENT_MB = 17


@dataclass(frozen=True)
class EmailConfig:
    host: str
    port: int
    user: str
    password: str
    sender: str  # EMAIL_FROM; defaults to ``user``
    allowed_domains: FrozenSet[str]  # lowercased, no leading '@'; empty = allow any
    max_attachment_bytes: int
    # Backend: "smtp" (Gmail, default) or "brevo" (Brevo HTTP API over HTTPS:443).
    # Brevo is the path that works on hosts which block outbound SMTP (e.g. Render).
    provider: str = "smtp"
    api_key: str = ""  # BREVO_API_KEY (only used when provider == "brevo")

    @property
    def is_configured(self) -> bool:
        """True when this backend has what it needs to send."""
        if self.provider == "brevo":
            return bool(self.api_key and self.sender)  # verified Brevo sender required
        return bool(self.user and self.password)


def _clean(value: Optional[str]) -> str:
    return (value or "").strip()


def email_enabled() -> bool:
    """True when a usable email backend is configured (Brevo HTTP API **or** SMTP).

    Default off. Brevo wins when ``BREVO_API_KEY`` is set (+ a verified ``EMAIL_FROM``
    sender); otherwise SMTP needs ``SMTP_USER`` + ``SMTP_PASSWORD``.
    """
    return load_config().is_configured


def _parse_allowed_domains(raw: Optional[str]) -> FrozenSet[str]:
    items = []
    for part in (raw or "").replace(";", ",").split(","):
        domain = part.strip().lower().lstrip("@")
        if domain:
            items.append(domain)
    return frozenset(items)


def _parse_port(raw: Optional[str]) -> int:
    try:
        return int(_clean(raw) or DEFAULT_PORT)
    except ValueError:
        return DEFAULT_PORT


def _parse_max_mb(raw: Optional[str]) -> int:
    try:
        mb = int(float(_clean(raw)))
    except ValueError:
        return DEFAULT_MAX_ATTACHMENT_MB
    return mb if mb > 0 else DEFAULT_MAX_ATTACHMENT_MB


def load_config() -> EmailConfig:
    """Build an :class:`EmailConfig` from the environment (no validation of secrets)."""
    user = _clean(os.environ.get("SMTP_USER"))
    # Gmail App Passwords are shown in space-separated groups; strip them.
    password = _clean(os.environ.get("SMTP_PASSWORD")).replace(" ", "")
    sender = _clean(os.environ.get("EMAIL_FROM")) or user
    api_key = _clean(os.environ.get("BREVO_API_KEY"))
    provider = "brevo" if api_key else "smtp"
    return EmailConfig(
        host=_clean(os.environ.get("SMTP_HOST")) or DEFAULT_HOST,
        port=_parse_port(os.environ.get("SMTP_PORT")),
        user=user,
        password=password,
        sender=sender,
        allowed_domains=_parse_allowed_domains(os.environ.get("EMAIL_ALLOWED_DOMAINS")),
        max_attachment_bytes=_parse_max_mb(os.environ.get("EMAIL_MAX_ATTACHMENT_MB")) * 1024 * 1024,
        provider=provider,
        api_key=api_key,
    )
