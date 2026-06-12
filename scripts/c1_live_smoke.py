"""Round C1 / B5 — live-Oracle smoke against a real instance (RISK-04 evidence).

Drives the **actual product code** — `OracleClient.run_select` (the SELECT-only
chokepoint), live introspection, a bind-parameterized report, CSV export, and a
safety rejection — against a real Oracle DB, using a least-privilege read-only
account (ADR-009). Connection comes from the git-ignored `.env` (`AOR_LIVE_*`);
the password is never printed.

Run from the repo root:  python scripts/c1_live_smoke.py
"""

from __future__ import annotations

import io
import os
import sys

from dotenv import load_dotenv

load_dotenv()  # repo .env → AOR_LIVE_* (+ APP_SECRET_KEY etc.)

from src.core.introspection import introspect_schema
from src.core.sql_safety import SqlSafetyError
from src.db import OracleClient, OracleConnectionConfig

_PASS, _FAIL = "PASS", "FAIL"
_results: list[tuple[str, str, str]] = []


def _record(step: str, ok: bool, detail: str = "") -> None:
    _results.append((step, _PASS if ok else _FAIL, detail))
    print(f"[{_PASS if ok else _FAIL}] {step}" + (f" — {detail}" if detail else ""))


def main() -> int:
    missing = [k for k in ("AOR_LIVE_HOST", "AOR_LIVE_SERVICE", "AOR_LIVE_USER", "AOR_LIVE_PASSWORD")
               if not os.getenv(k)]
    if missing:
        print(f"Missing env: {', '.join(missing)} — run the C1 §6 setup first.")
        return 2

    owner = (os.getenv("AOR_LIVE_OWNER") or "AOR_DEMO").upper()
    cfg = OracleConnectionConfig(
        host=os.environ["AOR_LIVE_HOST"],
        port=int(os.getenv("AOR_LIVE_PORT", "1521")),
        service_name=os.environ["AOR_LIVE_SERVICE"],
        sid=None,
        username=os.environ["AOR_LIVE_USER"],
        password=os.environ["AOR_LIVE_PASSWORD"],
    )
    client = OracleClient(cfg)

    # 1) Connect / test through the chokepoint.
    try:
        r = client.run_select("SELECT 1 AS one FROM dual")
        _record("connect+run_select", r.rows == [(1,)], f"{r.elapsed_seconds:.3f}s")
    except Exception as e:  # noqa: BLE001
        _record("connect+run_select", False, f"{type(e).__name__}: {e}")
        return 1  # nothing else will work without a connection

    # 2) Live introspection of the sample schema.
    try:
        ir = introspect_schema(client, owner=owner)
        tables = sorted(ir.schema.tables.keys())
        rels = len(ir.schema.relationships)  # FKs live at the schema level
        ok = {"DEPARTMENTS", "EMPLOYEES"}.issubset(set(tables)) and rels >= 1
        _record("introspection", ok, f"tables={tables} relationships={rels} warnings={ir.warnings}")
    except Exception as e:  # noqa: BLE001
        _record("introspection", False, f"{type(e).__name__}: {e}")

    # 3) Bind-parameterized report (bind passed as a value, never interpolated).
    try:
        sql = (f"SELECT first_name, last_name, salary FROM {owner}.employees "
               "WHERE department_id = :dept ORDER BY salary DESC")
        r = client.run_select(sql, binds={"dept": 20})
        ok = r.row_count == 2 and "SALARY" in [c.upper() for c in r.columns]
        _record("bound report", ok, f"rows={r.row_count} cols={r.columns}")
        # 4) Export the result to CSV (mirrors the app's export path).
        import pandas as pd
        buf = io.StringIO()
        pd.DataFrame(r.rows, columns=r.columns).to_csv(buf, index=False)
        csv = buf.getvalue()
        _record("CSV export", "Lovelace" in csv and "Turing" in csv, f"{len(csv)} bytes")
    except Exception as e:  # noqa: BLE001
        _record("bound report / export", False, f"{type(e).__name__}: {e}")

    # 5) Safety gate: a write must be rejected by the chokepoint, never reach the DB.
    for label, bad in (("UPDATE", f"UPDATE {owner}.employees SET salary = 0"),
                       ("FOR UPDATE", f"SELECT * FROM {owner}.employees FOR UPDATE")):
        try:
            client.run_select(bad)
            _record(f"safety rejects {label}", False, "NOT rejected — chokepoint bypass!")
        except SqlSafetyError as e:
            _record(f"safety rejects {label}", True, str(e)[:70])
        except Exception as e:  # noqa: BLE001
            _record(f"safety rejects {label}", False, f"wrong error {type(e).__name__}: {e}")

    failed = [s for s, v, _ in _results if v == _FAIL]
    print("\n=== VERDICT: " + ("ALL PASS ===" if not failed else f"{len(failed)} FAILED: {failed} ==="))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
