"""SMTP send orchestration for the email follow-up action (Phase 8, B2).

One entry point — :func:`send_report_email` — that validates recipients, builds
the message, sends it via Gmail SMTP (STARTTLS on 587, implicit SSL on 465),
**audit-logs the outcome (metadata only)**, and updates metrics. It never raises
for an infrastructure failure: it returns a :class:`SendResult` whose ``kind``
tells the UI exactly what to show.

Secret discipline: ``SMTP_PASSWORD`` only ever reaches :meth:`smtplib.SMTP.login`.
It is never placed in a ``SendResult``, an audit field, a log record, or any
return value. Transport/auth exceptions are logged server-side keyed by an
``error_id``; the caller gets only a generic message + that id — the same rule as
:func:`src.core.errors.sanitize_db_error_for_ui`, via ``GENERIC_EMAIL_DETAIL``.
"""

from __future__ import annotations

import smtplib
import ssl
from dataclasses import dataclass
from email.message import EmailMessage
from email.utils import parseaddr
from typing import List, Optional

import pandas as pd

from src.core import metrics
from src.core.errors import GENERIC_EMAIL_DETAIL, log_error, new_error_id
from src.core.logging_config import get_logger
from src.core.mailer.config import EmailConfig, load_config
from src.core.mailer.message import (
    EmailRejected,
    all_recipients,
    build_html_message,
    build_message,
    enforce_allowlist,
    normalize_format,
    parse_recipients,
)

_audit = get_logger("audit")
_SMTP_TIMEOUT = 30  # seconds


@dataclass(frozen=True)
class SendResult:
    """Outcome of a send. ``kind`` ∈ {``ok``, ``rejected``, ``error``}.

    - ``ok`` — delivered; ``message`` is a friendly summary.
    - ``rejected`` — user-actionable (bad recipient/domain/format/oversize/not
      configured); ``message`` is **safe to show verbatim**.
    - ``error`` — transport/auth failure; ``message`` is generic and carries an
      ``error_id`` (full detail is server-side only).
    """

    kind: str
    message: str
    error_id: Optional[str] = None
    recipients: int = 0
    attachment_bytes: int = 0

    @property
    def ok(self) -> bool:
        return self.kind == "ok"


def _attachment_size(msg: EmailMessage) -> int:
    for att in msg.iter_attachments():
        payload = att.get_payload(decode=True)
        return len(payload) if payload else 0
    return 0


def _transport_send(cfg: EmailConfig, msg: EmailMessage, envelope: List[str]) -> None:
    context = ssl.create_default_context()
    from_addr = parseaddr(cfg.sender)[1] or cfg.user
    if cfg.port == 465:
        with smtplib.SMTP_SSL(cfg.host, cfg.port, context=context, timeout=_SMTP_TIMEOUT) as server:
            server.login(cfg.user, cfg.password)
            server.send_message(msg, from_addr=from_addr, to_addrs=envelope)
    else:
        with smtplib.SMTP(cfg.host, cfg.port, timeout=_SMTP_TIMEOUT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(cfg.user, cfg.password)
            server.send_message(msg, from_addr=from_addr, to_addrs=envelope)


def send_report_email(
    *,
    to: str,
    subject: str,
    body: str,
    df: pd.DataFrame,
    attachment_format: str,
    cc: str = "",
    filename: Optional[str] = None,
    config: Optional[EmailConfig] = None,
) -> SendResult:
    """Validate, build, and send the report email. Returns a :class:`SendResult`.

    ``to`` / ``cc`` are free-form strings (comma/semicolon/whitespace separated).
    """
    cfg = config or load_config()
    if not (cfg.user and cfg.password):
        return SendResult(
            kind="rejected",
            message="Email is not configured — set SMTP_USER and SMTP_PASSWORD in .env.",
        )

    # --- validate + assemble (no network) --------------------------------- #
    try:
        fmt = normalize_format(attachment_format)
        to_list = parse_recipients(to)
        cc_list = parse_recipients(cc)
        if not to_list:
            raise EmailRejected("At least one recipient is required.")
        enforce_allowlist(to_list + cc_list, cfg.allowed_domains)
        msg = build_message(
            sender=cfg.sender, to=to_list, cc=cc_list, subject=subject, body=body,
            df=df, attachment_format=fmt, filename=filename,
            max_attachment_bytes=cfg.max_attachment_bytes,
        )
    except EmailRejected as exc:
        metrics.increment("emails_rejected")
        return SendResult(kind="rejected", message=str(exc))

    envelope = all_recipients(msg)
    size = _attachment_size(msg)
    audit_fields = {
        "to": to_list,
        "cc": cc_list,
        "subject": msg["Subject"],
        "attachment_format": fmt,
        "row_count": int(len(df)),
        "attachment_bytes": size,
    }

    # --- send (network) --------------------------------------------------- #
    try:
        _transport_send(cfg, msg, envelope)
    except Exception as exc:  # noqa: BLE001 - sanitize any transport/auth error
        error_id = new_error_id()
        log_error(exc, context="email-send", error_id=error_id, event="email_error")
        metrics.increment("emails_failed")
        _audit.warning("email_failed", extra={"extra_fields": {
            "event": "email_failed", "error_id": error_id, "outcome": "error", **audit_fields,
        }})
        return SendResult(kind="error", message=GENERIC_EMAIL_DETAIL, error_id=error_id,
                          recipients=len(envelope), attachment_bytes=size)

    metrics.increment("emails_sent")
    _audit.info("email_sent", extra={"extra_fields": {
        "event": "email_sent", "outcome": "sent", **audit_fields,
    }})
    size_text = f"{size / 1024:.1f} KB" if size >= 1024 else f"{size} bytes"
    return SendResult(
        kind="ok",
        message=f"Sent to {len(envelope)} recipient(s) - {fmt.upper()} attached ({size_text}).",
        recipients=len(envelope), attachment_bytes=size,
    )


def send_html_bundle_email(
    *,
    to: str,
    subject: str,
    body: str,
    html: str,
    cc: str = "",
    filename: Optional[str] = None,
    config: Optional[EmailConfig] = None,
) -> SendResult:
    """Send a cascading-report **HTML bundle** as an ``.html`` attachment (Phase 10,
    ADR-026). Mirrors :func:`send_report_email`'s validate -> build -> send -> audit
    flow but carries the prebuilt bundle instead of a DataFrame — **no LLM, no
    re-query**. Reuses every guard (allow-list, header-injection, size cap, audit).
    """
    cfg = config or load_config()
    if not (cfg.user and cfg.password):
        return SendResult(
            kind="rejected",
            message="Email is not configured — set SMTP_USER and SMTP_PASSWORD in .env.",
        )

    try:
        to_list = parse_recipients(to)
        cc_list = parse_recipients(cc)
        if not to_list:
            raise EmailRejected("At least one recipient is required.")
        enforce_allowlist(to_list + cc_list, cfg.allowed_domains)
        msg = build_html_message(
            sender=cfg.sender, to=to_list, cc=cc_list, subject=subject, body=body,
            html=html, filename=filename, max_attachment_bytes=cfg.max_attachment_bytes,
        )
    except EmailRejected as exc:
        metrics.increment("emails_rejected")
        return SendResult(kind="rejected", message=str(exc))

    envelope = all_recipients(msg)
    size = _attachment_size(msg)
    audit_fields = {
        "to": to_list,
        "cc": cc_list,
        "subject": msg["Subject"],
        "attachment_format": "html",
        "attachment_bytes": size,
    }

    try:
        _transport_send(cfg, msg, envelope)
    except Exception as exc:  # noqa: BLE001 - sanitize any transport/auth error
        error_id = new_error_id()
        log_error(exc, context="email-bundle-send", error_id=error_id, event="email_error")
        metrics.increment("emails_failed")
        _audit.warning("email_failed", extra={"extra_fields": {
            "event": "email_failed", "error_id": error_id, "outcome": "error", **audit_fields,
        }})
        return SendResult(kind="error", message=GENERIC_EMAIL_DETAIL, error_id=error_id,
                          recipients=len(envelope), attachment_bytes=size)

    metrics.increment("emails_sent")
    _audit.info("email_sent", extra={"extra_fields": {
        "event": "email_sent", "outcome": "sent", **audit_fields,
    }})
    size_text = f"{size / 1024:.1f} KB" if size >= 1024 else f"{size} bytes"
    return SendResult(
        kind="ok",
        message=f"Sent to {len(envelope)} recipient(s) - HTML report attached ({size_text}).",
        recipients=len(envelope), attachment_bytes=size,
    )
