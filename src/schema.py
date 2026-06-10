from __future__ import annotations

from dataclasses import dataclass, field
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