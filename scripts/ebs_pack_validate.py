"""Validate the curated EBS metadata packs against a real EBS instance (ITM-012).

For every table referenced by a pack — table notes (+ key columns), glossary
targets, and join endpoints — this checks the live Oracle data dictionary
(``ALL_TAB_COLUMNS``) to confirm the **table and each referenced column exist**.
It reuses the product's SELECT-only chokepoint (``OracleClient.run_select``), so
it can only read; it never writes.

The validator does **not** need an EBS instance to be *written* — only to be
*run*. When an EBS 12.2 environment is reachable (a customer/pilot dev/test, an
Oracle Vision demo, or an OCI EBS image), point a least-privilege read-only
account at it and run:

    # connection from env (or a git-ignored .env): EBS_HOST/PORT/SERVICE|SID/USER/PASSWORD
    python scripts/ebs_pack_validate.py            # validate all 5 modules
    python scripts/ebs_pack_validate.py AP GL      # validate selected modules

EBS base tables live in schemas (AP, GL, AR, PO, ONT, HZ, …); a properly
privileged reporting account sees them in ``ALL_TAB_COLUMNS`` regardless of
owner, so the lookup is by table name (the owner(s) found are reported).
"""

from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Set

# Allow running as a plain script from the repo root.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.ebs_packs import EbsPack, list_packs  # noqa: E402

_JOIN_ENDPOINT = re.compile(r"([A-Za-z0-9_]+)\.([A-Za-z0-9_]+)")

# A lookup returns the set of UPPERCASE column names found for a table (across
# any owner the account can see), or an empty set if the table is not found.
ColumnLookup = Callable[[str], Set[str]]


@dataclass
class TableResult:
    table: str
    found: bool
    missing_columns: List[str] = field(default_factory=list)
    owners: List[str] = field(default_factory=list)


@dataclass
class PackResult:
    module: str
    tables: List[TableResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(t.found and not t.missing_columns for t in self.tables)


def required_columns(pack: EbsPack) -> Dict[str, Set[str]]:
    """Aggregate every (table -> {columns}) the pack references: key columns,
    glossary targets, and both endpoints of each join hint. Column names are
    upper-cased to match the Oracle dictionary."""
    req: Dict[str, Set[str]] = {}

    def add(table: str, column: str = "") -> None:
        t = table.upper()
        req.setdefault(t, set())
        if column:
            req[t].add(column.upper())

    for t in pack.tables:
        add(t.table)
        for c in t.key_columns:
            add(t.table, c)
        for j in t.joins:
            for tbl, col in _JOIN_ENDPOINT.findall(j):
                add(tbl, col)
    for g in pack.glossary:
        add(g.table, g.column or "")
    return req


def validate_pack(pack: EbsPack, lookup: ColumnLookup) -> PackResult:
    result = PackResult(module=pack.module)
    for table, cols in sorted(required_columns(pack).items()):
        found_cols = lookup(table)
        if not found_cols:
            result.tables.append(TableResult(table=table, found=False))
            continue
        missing = sorted(c for c in cols if c not in found_cols)
        result.tables.append(TableResult(table=table, found=True, missing_columns=missing))
    return result


def _client_lookup(client) -> ColumnLookup:
    """A ColumnLookup backed by the live data dictionary via the chokepoint."""
    sql = "SELECT owner, column_name FROM all_tab_columns WHERE table_name = :t"
    owners_seen: Dict[str, List[str]] = {}

    def lookup(table: str) -> Set[str]:
        res = client.run_select(sql, binds={"t": table.upper()})
        cols: Set[str] = set()
        owners: Set[str] = set()
        for owner, column in res.rows:
            owners.add(str(owner))
            cols.add(str(column).upper())
        owners_seen[table.upper()] = sorted(owners)
        return cols

    lookup.owners_seen = owners_seen  # type: ignore[attr-defined]
    return lookup


def _print_report(results: List[PackResult]) -> bool:
    all_ok = True
    for r in results:
        print(f"\n=== {r.module} ===")
        for t in r.tables:
            if not t.found:
                print(f"  [MISSING TABLE] {t.table}")
                all_ok = False
            elif t.missing_columns:
                print(f"  [MISSING COLS ] {t.table}: {', '.join(t.missing_columns)}")
                all_ok = False
            else:
                print(f"  [OK]            {t.table}")
    print("\n" + ("=== VALIDATION: ALL PACK OBJECTS FOUND ===" if all_ok
                  else "=== VALIDATION: GAPS FOUND (see [MISSING ...] above) ==="))
    return all_ok


def main(argv: List[str]) -> int:
    from dotenv import load_dotenv
    load_dotenv()
    missing_env = [k for k in ("EBS_HOST", "EBS_USER", "EBS_PASSWORD")
                   if not os.getenv(k)] + (
        [] if (os.getenv("EBS_SERVICE") or os.getenv("EBS_SID")) else ["EBS_SERVICE or EBS_SID"])
    if missing_env:
        print(f"Missing env: {', '.join(missing_env)}. Set the EBS_* connection vars and re-run.")
        return 2

    from src.db import OracleClient, OracleConnectionConfig
    client = OracleClient(OracleConnectionConfig(
        host=os.environ["EBS_HOST"],
        port=int(os.getenv("EBS_PORT", "1521")),
        service_name=os.getenv("EBS_SERVICE"),
        sid=os.getenv("EBS_SID"),
        username=os.environ["EBS_USER"],
        password=os.environ["EBS_PASSWORD"],
    ))

    wanted = {m.upper() for m in argv} if argv else None
    packs = [p for p in list_packs() if wanted is None or p.module in wanted]
    lookup = _client_lookup(client)
    results = [validate_pack(p, lookup) for p in packs]
    return 0 if _print_report(results) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
