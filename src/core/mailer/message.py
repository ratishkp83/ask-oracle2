"""Recipient/subject validation + message assembly for the email action.

User-actionable rejections raise :class:`EmailRejected` — safe to display
verbatim, exactly like the SQL safety layer's rejection ``reason``. **Header
injection is impossible by construction:** any address or subject carrying a
CR/LF/control char is rejected, and the message is assembled with the stdlib
:class:`email.message.EmailMessage` (no hand-built header strings).

Attachments reuse the existing export helpers in :mod:`src.utils`, so CSV/Excel
serialization is identical to the download buttons.
"""

from __future__ import annotations

import re
from email.message import EmailMessage
from typing import Iterable, List, Optional, Sequence

import pandas as pd

from src.utils import dataframe_to_csv_bytes, dataframe_to_excel_bytes

# Pragmatic address check (not full RFC 5322): one '@', non-empty local part and
# a dotted domain, no whitespace/control chars. The point is to reject the
# obviously invalid and anything carrying CR/LF (the header-injection guard).
_ADDR_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
# All C0 control chars + DEL (incl. CR/LF/TAB/NUL). CR/LF are the header-injection
# vector; the wider class also enforces the "illegal char → rejected" contract (P8-R1-F2).
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")

_CSV = "csv"
_EXCEL = "excel"
_FORMATS = (_CSV, _EXCEL)
_MIME = {
    _CSV: ("text", "csv"),
    _EXCEL: ("application", "vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
}
_EXT = {_CSV: "csv", _EXCEL: "xlsx"}


class EmailRejected(Exception):
    """A user-actionable rejection — safe to display verbatim (no infra detail)."""


def validate_address(addr: str) -> str:
    """Return the trimmed address, or raise :class:`EmailRejected`."""
    a = (addr or "").strip()
    if not a:
        raise EmailRejected("Recipient address is empty.")
    if _CONTROL_RE.search(a):
        raise EmailRejected("Recipient address contains an illegal character.")
    if not _ADDR_RE.match(a):
        raise EmailRejected(f"Not a valid email address: {a}")
    return a


def parse_recipients(raw: str) -> List[str]:
    """Split a free-form To/CC string on commas/semicolons/whitespace.

    Returns validated addresses, deduped case-insensitively, in first-seen order.
    """
    if not raw:
        return []
    out: List[str] = []
    seen = set()
    for part in re.split(r"[,;\s]+", raw.strip()):
        if not part:
            continue
        a = validate_address(part)
        key = a.lower()
        if key not in seen:
            seen.add(key)
            out.append(a)
    return out


def enforce_allowlist(addresses: Iterable[str], allowed_domains: Iterable[str]) -> None:
    """Raise :class:`EmailRejected` if any address is outside the allow-list.

    An empty ``allowed_domains`` means *allow any* (the default).
    """
    allowed = {d.lower() for d in allowed_domains}
    if not allowed:
        return
    for a in addresses:
        domain = a.rsplit("@", 1)[-1].lower()
        if domain not in allowed:
            raise EmailRejected(f"Recipient domain not allowed by policy: {domain}")


def sanitize_subject(subject: str, *, max_len: int = 200) -> str:
    """Collapse control chars to spaces and cap the length (header-injection-safe)."""
    return _CONTROL_RE.sub(" ", (subject or "").strip())[:max_len]


def normalize_format(attachment_format: str) -> str:
    """Coerce a format string to ``'csv'`` or ``'excel'``, or raise."""
    fmt = (attachment_format or "").strip().lower()
    if fmt in ("xlsx", "xls"):
        fmt = _EXCEL
    if fmt not in _FORMATS:
        raise EmailRejected("Attachment format must be 'csv' or 'excel'.")
    return fmt


def _attachment_bytes(df: pd.DataFrame, fmt: str) -> bytes:
    return dataframe_to_csv_bytes(df) if fmt == _CSV else dataframe_to_excel_bytes(df)


def build_message(
    *,
    sender: str,
    to: Sequence[str],
    cc: Sequence[str] = (),
    subject: str,
    body: str,
    df: pd.DataFrame,
    attachment_format: str,
    filename: Optional[str] = None,
    max_attachment_bytes: Optional[int] = None,
) -> EmailMessage:
    """Assemble the outgoing message with the report attached.

    Re-validates every recipient (defense in depth) and enforces the size cap
    *before* any network use. Raises :class:`EmailRejected` for anything the
    user can fix (no recipients, bad address, unsupported format, oversize).
    """
    fmt = normalize_format(attachment_format)
    to_list = [validate_address(a) for a in to]
    cc_list = [validate_address(a) for a in cc]
    if not to_list:
        raise EmailRejected("At least one recipient is required.")

    data = _attachment_bytes(df, fmt)
    if max_attachment_bytes is not None and len(data) > max_attachment_bytes:
        raise EmailRejected(
            f"Attachment is {len(data) / 1024 / 1024:.1f} MB, over the "
            f"{max_attachment_bytes / 1024 / 1024:.0f} MB limit. "
            "Narrow the query (fewer rows/columns) and try again."
        )

    msg = EmailMessage()
    # The From is operator-set (EMAIL_FROM) and may carry a display name, so it
    # isn't address-validated — strip any control chars defensively (P8-R1-F4).
    msg["From"] = _CONTROL_RE.sub("", sender)
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = sanitize_subject(subject)
    msg.set_content(body or "")

    maintype, subtype = _MIME[fmt]
    name = filename or f"report.{_EXT[fmt]}"
    if not name.lower().endswith("." + _EXT[fmt]):
        name = f"{name}.{_EXT[fmt]}"
    msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=name)
    return msg


def build_html_message(
    *,
    sender: str,
    to: Sequence[str],
    cc: Sequence[str] = (),
    subject: str,
    body: str,
    html: str,
    filename: Optional[str] = None,
    max_attachment_bytes: Optional[int] = None,
) -> EmailMessage:
    """Assemble a message carrying a cascading-report **HTML bundle** as an
    ``.html`` attachment (Phase 10, ADR-026).

    The bundle is the already-built document — **no DataFrame, no re-query**. Same
    guards as :func:`build_message`: every recipient re-validated, the subject and
    From control-char-stripped (header-injection-safe), and the size cap enforced
    *before* any network use. Raises :class:`EmailRejected` for user-fixable errors.
    """
    to_list = [validate_address(a) for a in to]
    cc_list = [validate_address(a) for a in cc]
    if not to_list:
        raise EmailRejected("At least one recipient is required.")

    data = (html or "").encode("utf-8")
    if not data:
        raise EmailRejected("The report is empty.")
    if max_attachment_bytes is not None and len(data) > max_attachment_bytes:
        raise EmailRejected(
            f"Report is {len(data) / 1024 / 1024:.1f} MB, over the "
            f"{max_attachment_bytes / 1024 / 1024:.0f} MB limit. "
            "Narrow the report (fewer breakdowns/rows) and try again."
        )

    msg = EmailMessage()
    msg["From"] = _CONTROL_RE.sub("", sender)
    msg["To"] = ", ".join(to_list)
    if cc_list:
        msg["Cc"] = ", ".join(cc_list)
    msg["Subject"] = sanitize_subject(subject)
    msg.set_content(body or "Your cascading report is attached as an HTML file.")

    name = filename or "cascading-report.html"
    if not name.lower().endswith(".html"):
        name = f"{name}.html"
    msg.add_attachment(data, maintype="text", subtype="html", filename=name)
    return msg


def all_recipients(msg: EmailMessage) -> List[str]:
    """Flatten To + Cc into a single envelope list (used by the sender)."""
    out: List[str] = []
    for header in ("To", "Cc"):
        raw = msg.get(header)
        if raw:
            out.extend(a.strip() for a in str(raw).split(",") if a.strip())
    return out
