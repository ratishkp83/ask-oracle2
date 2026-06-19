"""Migrate the local Oracle XE schema + data into PostgreSQL / Supabase.

Reads tables from XE **read-only** (connection from the git-ignored ``.env`` —
``AOR_LIVE_*``, the same vars ``c1_live_smoke.py`` uses) and emits a single
Postgres ``.sql`` file: per-table ``DROP``/``CREATE`` (Oracle→Postgres type
mapping, **lower-cased** identifiers — Postgres convention) + batched ``INSERT``s +
``FK`` constraints added at the end (so data load order doesn't matter), wrapped in
one transaction. Run that file in the **Supabase SQL editor**.

Optionally ``--apply`` executes it against Supabase using ``PG_*`` env vars — those
MUST point at a role allowed to CREATE/INSERT (the migration writes; it is NOT the
read-only app role).

Usage (from the repo root, with the venv active):
  python scripts/xe_to_supabase.py                       # -> scripts/out/supabase_migration.sql
  python scripts/xe_to_supabase.py --tables EMPLOYEES,DEPARTMENTS,SALES
  python scripts/xe_to_supabase.py --apply               # also run it against Supabase (PG_*)
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

from src.core.config import load_safety_limits  # noqa: E402
from src.core.introspection import introspect_schema  # noqa: E402
from src.db import OracleClient, OracleConnectionConfig  # noqa: E402
from src.schema import ColumnDefinition, Schema  # noqa: E402

load_dotenv()


# --------------------------------------------------------------------------- #
# Oracle → Postgres mapping
# --------------------------------------------------------------------------- #
def pg_type(c: ColumnDefinition) -> str:
    t = (c.data_type or "").upper()
    if t in ("VARCHAR2", "NVARCHAR2", "VARCHAR", "CHAR", "NCHAR"):
        n = c.data_length or 255
        return f"varchar({n})"
    if t in ("CLOB", "NCLOB", "LONG"):
        return "text"
    if t == "NUMBER":
        if c.data_scale and c.data_scale > 0:
            return f"numeric({c.data_precision or 38},{c.data_scale})"
        if c.data_precision:
            return "integer" if c.data_precision <= 9 else "bigint"
        return "numeric"
    if t in ("FLOAT", "BINARY_FLOAT", "BINARY_DOUBLE"):
        return "double precision"
    if t == "DATE" or t.startswith("TIMESTAMP"):
        return "timestamp"
    if t in ("BLOB", "RAW", "LONG RAW"):
        return "bytea"
    return "text"  # safe fallback


def ident(name: str) -> str:
    """Lower-case identifier (Postgres convention) — assumes simple A-Z0-9_ names."""
    return name.strip().lower()


def lit(v: object) -> str:
    """A Postgres SQL literal for a value read from Oracle."""
    if v is None:
        return "NULL"
    if hasattr(v, "read"):  # an oracledb LOB
        try:
            v = v.read()
        except Exception:  # noqa: BLE001
            v = str(v)
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float, Decimal)):
        return str(v)
    if isinstance(v, (datetime, date)):
        return "'" + v.isoformat(sep=" ") + "'"
    if isinstance(v, (bytes, bytearray)):
        return "'\\x" + bytes(v).hex() + "'"
    return "'" + str(v).replace("'", "''") + "'"


# --------------------------------------------------------------------------- #
# DDL + data
# --------------------------------------------------------------------------- #
def create_table_sql(schema: Schema, table: str) -> str:
    tdef = schema.tables[table]
    cols = []
    for c in tdef.columns:
        null = "" if (c.nullable is None or c.nullable) else " NOT NULL"
        cols.append(f"  {ident(c.column_name)} {pg_type(c)}{null}")
    pk = tdef.primary_keys()
    if pk:
        cols.append("  PRIMARY KEY (" + ", ".join(ident(c) for c in pk) + ")")
    body = ",\n".join(cols)
    return (
        f"DROP TABLE IF EXISTS {ident(table)} CASCADE;\n"
        f"CREATE TABLE {ident(table)} (\n{body}\n);\n"
    )


def insert_sql(table: str, columns: List[str], rows: List[tuple], batch: int = 100) -> str:
    if not rows:
        return ""
    col_list = ", ".join(ident(c) for c in columns)
    out: List[str] = []
    for i in range(0, len(rows), batch):
        chunk = rows[i : i + batch]
        values = ",\n".join("(" + ", ".join(lit(v) for v in row) + ")" for row in chunk)
        out.append(f"INSERT INTO {ident(table)} ({col_list}) VALUES\n{values};")
    return "\n".join(out) + "\n"


def fk_sql(schema: Schema) -> str:
    lines: List[str] = []
    for i, r in enumerate(schema.relationships):
        if not (r.from_table and r.from_column and r.to_table and r.to_column):
            continue
        name = ident(f"{r.from_table}_{r.from_column}_fk_{i}")[:60]
        lines.append(
            f"ALTER TABLE {ident(r.from_table)} ADD CONSTRAINT {name} "
            f"FOREIGN KEY ({ident(r.from_column)}) "
            f"REFERENCES {ident(r.to_table)} ({ident(r.to_column)});"
        )
    return ("\n".join(lines) + "\n") if lines else ""


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description="Migrate Oracle XE → Postgres/Supabase.")
    ap.add_argument("--tables", help="Comma-separated table names (default: all in the schema).")
    ap.add_argument("--out", default=os.path.join("scripts", "out", "supabase_migration.sql"))
    ap.add_argument("--apply", action="store_true", help="Also execute against Supabase (PG_* env).")
    args = ap.parse_args()

    need = [k for k in ("AOR_LIVE_HOST", "AOR_LIVE_SERVICE", "AOR_LIVE_USER", "AOR_LIVE_PASSWORD")
            if not os.getenv(k)]
    if need:
        print(f"Missing XE connection env vars in .env: {', '.join(need)}", file=sys.stderr)
        return 2
    owner = (os.getenv("AOR_LIVE_OWNER") or "AOR_DEMO").upper()

    client = OracleClient(OracleConnectionConfig(
        host=os.environ["AOR_LIVE_HOST"],
        port=int(os.getenv("AOR_LIVE_PORT", "1521")),
        service_name=os.environ["AOR_LIVE_SERVICE"],
        sid=None,
        username=os.environ["AOR_LIVE_USER"],
        password=os.environ["AOR_LIVE_PASSWORD"],
        current_schema=owner,
    ))
    # Permissive caps for a one-off admin migration (owner-run, read-only).
    limits = load_safety_limits().model_copy(
        update={"max_rows": 5_000_000, "max_result_bytes": 2_000_000_000, "max_execution_seconds": 600}
    )

    print(f"Introspecting {owner} on XE …", file=sys.stderr)
    schema = introspect_schema(client, owner=owner, limits=limits).schema
    tables = sorted(schema.tables)
    if args.tables:
        want = {t.strip().upper() for t in args.tables.split(",") if t.strip()}
        tables = [t for t in tables if t.upper() in want]
    if not tables:
        print("No matching tables found.", file=sys.stderr)
        return 1

    parts: List[str] = [
        f"-- Migration of Oracle XE schema '{owner}' → PostgreSQL/Supabase\n"
        f"-- Generated by scripts/xe_to_supabase.py. Identifiers lower-cased.\n"
        "BEGIN;\n",
    ]
    total_rows = 0
    for t in tables:
        parts.append(f"\n-- ===== {ident(t)} =====\n")
        parts.append(create_table_sql(schema, t))
        res = client.run_select(f'SELECT * FROM "{owner}"."{t}"', limits=limits)
        total_rows += res.row_count
        parts.append(insert_sql(t, res.columns, res.rows))
        print(f"  {t}: {res.row_count} rows{' (TRUNCATED!)' if res.truncated else ''}", file=sys.stderr)

    fks = fk_sql(schema)
    if fks:
        parts.append("\n-- ===== foreign keys =====\n")
        parts.append(fks)
    parts.append("\nCOMMIT;\n")
    sql = "".join(parts)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(sql)
    print(f"\nWrote {args.out} — {len(tables)} tables, {total_rows} rows.", file=sys.stderr)
    print("Run it in the Supabase SQL editor (or re-run with --apply).", file=sys.stderr)

    if args.apply:
        _apply_to_supabase(sql)
    return 0


def _apply_to_supabase(sql: str) -> None:
    need = [k for k in ("PG_HOST", "PG_DATABASE", "PG_USER", "PG_PASSWORD") if not os.getenv(k)]
    if need:
        print(f"--apply needs PG_* env vars: {', '.join(need)}", file=sys.stderr)
        return
    import psycopg2  # lazy

    print("Applying to Supabase (PG_* — must allow CREATE/INSERT) …", file=sys.stderr)
    conn = psycopg2.connect(
        host=os.environ["PG_HOST"], port=int(os.getenv("PG_PORT", "5432")),
        dbname=os.environ["PG_DATABASE"], user=os.environ["PG_USER"],
        password=os.environ["PG_PASSWORD"], sslmode=os.getenv("PG_SSLMODE", "require"),
        connect_timeout=15,
    )
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        print("Applied successfully.", file=sys.stderr)
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
