"""Email follow-up action (Phase 8): email a report result via Gmail SMTP.

A sibling to the existing CSV/Excel export — after a report runs, the user can
send the result to recipient(s) they choose, with the output attached. Opt-in
(``email_enabled()``); user-initiated and reviewed (never auto-sent); no LLM on
this path (the schema-redaction tripwire is untouched).

Public surface:
- ``email_enabled`` / ``load_config`` / ``EmailConfig`` — opt-in env config.
- ``detect_recipient_candidates`` — smart quick-pick from the result columns.
- ``EmailRejected`` — user-actionable rejection (safe to show verbatim).
- ``send_report_email`` / ``SendResult`` — the orchestrated SMTP send (added in B2).
"""

from __future__ import annotations

from src.core.mailer.config import EmailConfig, email_enabled, load_config
from src.core.mailer.message import EmailRejected
from src.core.mailer.recipients import detect_recipient_candidates

__all__ = [
    "EmailConfig",
    "email_enabled",
    "load_config",
    "EmailRejected",
    "detect_recipient_candidates",
]
