from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional, Tuple
import pandas as pd


@dataclass
class ColumnDefinition:
    table_name: str
    column_name: str
    data_type: Optional[str] = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    references_table: Optional[str] = None
    references_column: Optional[str] = None


@dataclass
class RelationshipDefinition:
    from_table: str
    from_column: str
    to_table: str
    to_column: str
    relationship_type: Optional[str] = None  # one-to-many, many-to-one, etc.


@dataclass
class TableDefinition:
    name: str
    columns: List[ColumnDefinition] = field(default_factory=list)

    def primary_keys(self) -> List[str]:
        return [c.column_name for c in self.columns if c.is_primary_key]

    def foreign_keys(self) -> List[Tuple[str, str, str]]:
        pairs: List[Tuple[str, str, str]] = []
        for c in self.columns:
            if c.is_foreign_key and c.references_table and c.references_column:
                pairs.append((c.column_name, c.references_table, c.references_column))
        return pairs


@dataclass
class Schema:
    tables: Dict[str, TableDefinition] = field(default_factory=dict)
    relationships: List[RelationshipDefinition] = field(default_factory=list)

    def list_tables(self) -> List[str]:
        return sorted(self.tables.keys())

    def list_columns(self, table_name: str) -> List[str]:
        table = self.tables.get(table_name)
        if not table:
            return []
        return [c.column_name for c in table.columns]

    def to_compact_markdown(self) -> str:
        lines: List[str] = ["Schema Overview:"]
        for tname in self.list_tables():
            table = self.tables[tname]
            lines.append(f"- {tname}")
            for col in table.columns:
                flags = []
                if col.is_primary_key:
                    flags.append("PK")
                if col.is_foreign_key:
                    flags.append("FK")
                flag_txt = f" ({', '.join(flags)})" if flags else ""
                dtype = f"[{col.data_type}]" if col.data_type else ""
                ref = (
                    f" -> {col.references_table}.{col.references_column}" if col.references_table and col.references_column else ""
                )
                lines.append(f"  - {col.column_name} {dtype}{flag_txt}{ref}")
        if self.relationships:
            lines.append("Relationships:")
            for r in self.relationships:
                rel = r.relationship_type or ""
                reltxt = f" ({rel})" if rel else ""
                lines.append(
                    f"- {r.from_table}.{r.from_column} -> {r.to_table}.{r.to_column}{reltxt}"
                )
        return "\n".join(lines)


REQUIRED_SCHEMA_COLUMNS = {
    "table_name",
    "column_name",
    "data_type",
    "is_primary_key",
    "is_foreign_key",
    "references_table",
    "references_column",
}

RELATIONSHIP_COLUMNS = {
    "from_table",
    "from_column",
    "to_table",
    "to_column",
    "relationship_type",
}


def _normalize_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    s = str(value).strip().lower()
    return s in {"1", "true", "t", "yes", "y"}


def parse_schema_dataframe(df: pd.DataFrame) -> Schema:
    missing = [c for c in REQUIRED_SCHEMA_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Schema file missing required columns: {', '.join(missing)}. Required: {', '.join(sorted(REQUIRED_SCHEMA_COLUMNS))}"
        )

    schema = Schema()
    # Normalize boolean-like fields
    df = df.copy()
    df["is_primary_key"] = df["is_primary_key"].apply(_normalize_bool)
    df["is_foreign_key"] = df["is_foreign_key"].apply(_normalize_bool)

    for _, row in df.iterrows():
        table_name = str(row["table_name"]).strip()
        column = ColumnDefinition(
            table_name=table_name,
            column_name=str(row["column_name"]).strip(),
            data_type=str(row["data_type"]).strip() if not pd.isna(row["data_type"]) else None,
            is_primary_key=bool(row["is_primary_key"]),
            is_foreign_key=bool(row["is_foreign_key"]),
            references_table=(str(row["references_table"]).strip() if not pd.isna(row["references_table"]) else None),
            references_column=(str(row["references_column"]).strip() if not pd.isna(row["references_column"]) else None),
        )
        if table_name not in schema.tables:
            schema.tables[table_name] = TableDefinition(name=table_name, columns=[])
        schema.tables[table_name].columns.append(column)

    return schema


def parse_relationships_dataframe(df: pd.DataFrame) -> List[RelationshipDefinition]:
    missing = [c for c in RELATIONSHIP_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"Relationships file missing required columns: {', '.join(missing)}. Required: {', '.join(sorted(RELATIONSHIP_COLUMNS))}"
        )

    relationships: List[RelationshipDefinition] = []
    for _, row in df.iterrows():
        relationships.append(
            RelationshipDefinition(
                from_table=str(row["from_table"]).strip(),
                from_column=str(row["from_column"]).strip(),
                to_table=str(row["to_table"]).strip(),
                to_column=str(row["to_column"]).strip(),
                relationship_type=(
                    str(row["relationship_type"]).strip() if not pd.isna(row["relationship_type"]) else None
                ),
            )
        )
    return relationships


def attach_relationships(schema: Schema, relationships: List[RelationshipDefinition]) -> Schema:
    schema.relationships = relationships
    # Where possible, mark foreign keys on the columns based on relationships
    index: Dict[Tuple[str, str], ColumnDefinition] = {}
    for t in schema.tables.values():
        for c in t.columns:
            index[(t.name, c.column_name)] = c

    for r in relationships:
        key = (r.from_table, r.from_column)
        if key in index:
            col = index[key]
            col.is_foreign_key = True
            col.references_table = r.to_table
            col.references_column = r.to_column
    return schema


# --------------------------------------------------------------------------- #
# Data-dictionary helpers (Phase 5) — pure functions over a Schema, no DB.
# --------------------------------------------------------------------------- #
def table_detail(schema: Schema, table_name: str) -> List[ColumnDefinition]:
    """Full column detail for one table (empty list if unknown)."""
    table = schema.tables.get(table_name)
    return list(table.columns) if table else []


def find_columns(
    schema: Schema,
    query: str = "",
    *,
    data_type: Optional[str] = None,
    pk: Optional[bool] = None,
    fk: Optional[bool] = None,
) -> List[ColumnDefinition]:
    """Search columns by name substring (table or column) + optional filters.

    ``data_type`` matches as a case-insensitive substring (e.g. "char" → VARCHAR2).
    ``pk`` / ``fk`` filter on the primary/foreign-key flags when not ``None``.
    """
    q = (query or "").strip().lower()
    dt = (data_type or "").strip().lower()
    out: List[ColumnDefinition] = []
    for table in schema.tables.values():
        for col in table.columns:
            if q and q not in col.column_name.lower() and q not in col.table_name.lower():
                continue
            if dt and dt not in (col.data_type or "").lower():
                continue
            if pk is not None and col.is_primary_key != pk:
                continue
            if fk is not None and col.is_foreign_key != fk:
                continue
            out.append(col)
    out.sort(key=lambda c: (c.table_name, c.column_name))
    return out


def references_out(schema: Schema, table_name: str) -> List[Tuple[str, str, str]]:
    """FKs this table declares: ``[(from_column, to_table, to_column)]``."""
    out: List[Tuple[str, str, str]] = []
    seen: set = set()
    table = schema.tables.get(table_name)
    if table:
        for col in table.columns:
            if col.is_foreign_key and col.references_table and col.references_column:
                key = (col.column_name, col.references_table, col.references_column)
                if key not in seen:
                    seen.add(key)
                    out.append(key)
    for r in schema.relationships:
        if r.from_table == table_name:
            key = (r.from_column, r.to_table, r.to_column)
            if key not in seen:
                seen.add(key)
                out.append(key)
    out.sort()
    return out


def referenced_by(schema: Schema, table_name: str) -> List[Tuple[str, str, str]]:
    """Where-used: other tables' FKs that point AT this table.

    Returns ``[(from_table, from_column, to_column)]`` where ``to_column`` is on
    ``table_name``.
    """
    out: List[Tuple[str, str, str]] = []
    seen: set = set()
    for table in schema.tables.values():
        for col in table.columns:
            if col.is_foreign_key and col.references_table == table_name and col.references_column:
                key = (col.table_name, col.column_name, col.references_column)
                if key not in seen:
                    seen.add(key)
                    out.append(key)
    for r in schema.relationships:
        if r.to_table == table_name:
            key = (r.from_table, r.from_column, r.to_column)
            if key not in seen:
                seen.add(key)
                out.append(key)
    out.sort()
    return out


# --------------------------------------------------------------------------- #
# Serialization (Phase 5) — metadata only; no data values.
# --------------------------------------------------------------------------- #
def schema_to_dict(schema: Schema) -> Dict[str, object]:
    return {
        "tables": {name: [asdict(c) for c in t.columns] for name, t in schema.tables.items()},
        "relationships": [asdict(r) for r in schema.relationships],
    }


def _opt_str(value: object) -> Optional[str]:
    return str(value) if value is not None else None


def schema_from_dict(data: object) -> Schema:
    """Reconstruct a Schema, reading **only** known table/column/relationship
    fields and ignoring anything else.

    This is deliberately tolerant and whitelist-based: it never raises on
    malformed input, and any extra keys in the incoming dict (e.g. injected
    secrets, row data, connection strings) are **dropped** — which is what
    enforces the "metadata only" guarantee when a definition arrives from an
    untrusted ``POST /schemas`` body (see ADR-011, review F-1/F-3).
    """
    schema = Schema()
    if not isinstance(data, dict):
        return schema

    tables = data.get("tables")
    if isinstance(tables, dict):
        for name, cols in tables.items():
            tname = str(name)
            columns: List[ColumnDefinition] = []
            if isinstance(cols, list):
                for c in cols:
                    if not isinstance(c, dict):
                        continue
                    columns.append(
                        ColumnDefinition(
                            table_name=str(c.get("table_name") or tname),
                            column_name=str(c.get("column_name") or ""),
                            data_type=_opt_str(c.get("data_type")),
                            is_primary_key=bool(c.get("is_primary_key", False)),
                            is_foreign_key=bool(c.get("is_foreign_key", False)),
                            references_table=_opt_str(c.get("references_table")),
                            references_column=_opt_str(c.get("references_column")),
                        )
                    )
            schema.tables[tname] = TableDefinition(name=tname, columns=columns)

    rels = data.get("relationships")
    if isinstance(rels, list):
        for r in rels:
            if not isinstance(r, dict):
                continue
            schema.relationships.append(
                RelationshipDefinition(
                    from_table=str(r.get("from_table") or ""),
                    from_column=str(r.get("from_column") or ""),
                    to_table=str(r.get("to_table") or ""),
                    to_column=str(r.get("to_column") or ""),
                    relationship_type=_opt_str(r.get("relationship_type")),
                )
            )
    return schema