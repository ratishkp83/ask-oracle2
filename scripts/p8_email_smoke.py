"""Phase 8 / B4 - live email smoke (a real send through the product code).

Sends ONE real email with a sample report attached, exercising the actual
``send_report_email`` path: recipient validation, allow-list, message assembly,
Gmail SMTP (STARTTLS), the audit log, and metrics. Credentials come from the
git-ignored ``.env`` (``SMTP_USER`` / ``SMTP_PASSWORD`` ...); the password is
never printed.

Run from the repo root:
    python scripts/p8_email_smoke.py you@example.com
(or set SMOKE_EMAIL_TO in .env and run with no argument)
"""

from __future__ import annotations

import os
import sys

import pandas as pd
from dotenv import load_dotenv

load_dotenv()  # repo .env -> SMTP_* (+ SMOKE_EMAIL_TO)

from src.core.mailer import email_enabled, send_report_email


def main() -> int:
    if not email_enabled():
        print("Email not configured - set SMTP_USER and SMTP_PASSWORD in .env first.")
        return 2

    to = sys.argv[1] if len(sys.argv) > 1 else os.getenv("SMOKE_EMAIL_TO", "")
    if not to:
        print("Usage: python scripts/p8_email_smoke.py <recipient@example.com>")
        print("       (or set SMOKE_EMAIL_TO in .env)")
        return 2

    df = pd.DataFrame(
        {
            "vendor": ["Acme Corp", "Globex", "Initech"],
            "open_invoices": [12, 5, 23],
            "amount_usd": [48230.55, 9120.00, 187650.10],
            "contact": ["ap@acme.example", "ar@globex.example", "ap@initech.example"],
        }
    )

    print(f"Sending sample report ({len(df)} rows) to {to} ...")
    result = send_report_email(
        to=to,
        subject="Ask Oracle Reports - sample report (live smoke)",
        body=(
            "This is a live smoke test of the email follow-up action.\n"
            "The attached CSV is a sample report output."
        ),
        df=df,
        attachment_format="csv",
    )

    print(f"  kind={result.kind}  recipients={result.recipients}  bytes={result.attachment_bytes}")
    print(f"  message: {result.message}")
    if result.error_id:
        print(f"  error_id: {result.error_id} (full detail in the server logs)")
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
