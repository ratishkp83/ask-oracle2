from __future__ import annotations

import os
import re
import sys
from typing import Dict, List, Optional, Tuple

# Make the repo root importable so `streamlit run src/app.py` works from any CWD.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.db import OracleClient, OracleConnectionConfig
from src.core.profiles import JsonFileProfileStore, ProfileCreate, ProfilePublic
from src.core.crypto import SecretConfigError
from src.schema import (
    ColumnDefinition,
    Schema,
    attach_relationships,
    find_columns,
    parse_relationships_dataframe,
    parse_schema_dataframe,
    referenced_by,
    references_out,
    schema_from_dict,
    schema_to_dict,
    table_detail,
)
from src.core.schema_store import JsonFileSchemaStore
from src.core.introspection import introspect_schema
from src.core.mailer import (
    detect_recipient_candidates,
    email_enabled,
    send_report_email,
)
from src.nl2sql import (
    DEFAULT_GROQ_MODEL,
    DEFAULT_OPENAI_MODEL,
    LLMConfig,
    generate_sql_from_nl,
)
from src.utils import read_tabular_file, dataframe_to_csv_bytes, dataframe_to_excel_bytes
from src.storage import migrate_legacy_connection
from src.core.reports import (
    JsonFileReportStore,
    ReportCreate,
    ReportParam,
    coerce_report_binds,
)
from src.core.templates import get_template, list_templates
from src.core.ebs_packs import get_pack, list_packs
from src.core.logging_config import configure_logging
from src.core.errors import log_error_for_ui, sanitize_db_error_for_ui
from src.core.sql_safety import SqlSafetyError

load_dotenv()

# Structured logging to stdout. Idempotent — safe across Streamlit re-runs.
configure_logging()

st.set_page_config(page_title="Ask Oracle Reports", layout="wide")

# --- session state -------------------------------------------------------- #
if "schema" not in st.session_state:
    st.session_state.schema = None  # type: Optional[Schema]
if "schema_source" not in st.session_state:
    st.session_state.schema_source = "upload"
if "conn_config" not in st.session_state:
    # One-time import of any legacy connection.json, then it is deleted (ITM-006).
    st.session_state.conn_config = migrate_legacy_connection() or {}
if "last_results" not in st.session_state:
    st.session_state.last_results = None  # type: Optional[pd.DataFrame]
if "generated_sql" not in st.session_state:
    st.session_state.generated_sql = ""
if "nl_explanation" not in st.session_state:
    st.session_state.nl_explanation = None
if "nl_confidence" not in st.session_state:
    st.session_state.nl_confidence = None
if "llm_config" not in st.session_state:
    st.session_state.llm_config = None  # type: Optional[LLMConfig]


def get_store() -> JsonFileProfileStore:
    return JsonFileProfileStore()


def get_report_store() -> JsonFileReportStore:
    return JsonFileReportStore()


def get_schema_store() -> JsonFileSchemaStore:
    return JsonFileSchemaStore()


_BIND_RE = re.compile(r":([A-Za-z_][A-Za-z0-9_]*)")


def _detect_params(sql: str) -> List[str]:
    """Unique `:bind` names in declaration order, for the save-as-report form."""
    seen: List[str] = []
    for name in _BIND_RE.findall(sql or ""):
        if name not in seen:
            seen.append(name)
    return seen


def _resolved_to_cfg(resolved) -> OracleConnectionConfig:
    return OracleConnectionConfig(
        host=resolved.host,
        port=resolved.port,
        service_name=resolved.service_name,
        sid=resolved.sid,
        username=resolved.username,
        password=resolved.password,
    )


def _try_connect(cfg: OracleConnectionConfig) -> Tuple[bool, str]:
    try:
        result = OracleClient(cfg).run_select("SELECT 1 FROM DUAL")
        return True, f"Connected successfully in {result.elapsed_seconds:.2f}s"
    except Exception as e:  # noqa: BLE001 - driver/connection error: sanitize (ITM-015)
        error_id, msg = sanitize_db_error_for_ui(e, context="ui-test-connection")
        return False, f"Connection failed — {msg} (ref: {error_id})"


# --------------------------------------------------------------------------- #
# Sidebar: active connection (saved profile or manual entry)
# --------------------------------------------------------------------------- #
def _draw_manual_connection() -> Optional[OracleConnectionConfig]:
    cfg = st.session_state.conn_config
    host = st.sidebar.text_input("Host", value=str(cfg.get("host", "")))
    port = st.sidebar.number_input("Port", min_value=1, max_value=65535, value=int(cfg.get("port", 1521)))
    service_name = st.sidebar.text_input("Service Name (preferred)", value=str(cfg.get("service_name") or ""))
    sid = st.sidebar.text_input("SID (optional)", value=str(cfg.get("sid") or ""))
    username = st.sidebar.text_input("Username", value=str(cfg.get("username", "")))
    password = st.sidebar.text_input("Password", value=str(cfg.get("password", "")), type="password")

    test_clicked = st.sidebar.button("Test", width="stretch")
    st.sidebar.caption(
        "Manual entry is for this session only. To store a connection, add a "
        "**profile** in Connections (encrypted at rest)."
    )

    cfg_obj: Optional[OracleConnectionConfig] = None
    if host and username and password and (service_name or sid):
        cfg_obj = OracleConnectionConfig(
            host=host,
            port=int(port),
            service_name=service_name or None,
            sid=sid or None,
            username=username,
            password=password,
        )

    if test_clicked:
        if cfg_obj:
            ok, msg = _try_connect(cfg_obj)
            (st.sidebar.success if ok else st.sidebar.error)(msg)
        else:
            st.sidebar.error("Fill host, username, password, and service name or SID.")

    return cfg_obj


def draw_sidebar_connection() -> Optional[OracleConnectionConfig]:
    st.sidebar.header("Active Connection")
    store = get_store()
    try:
        profiles = store.list()
    except Exception as e:  # noqa: BLE001
        st.sidebar.error(f"Could not load profiles: {e}")
        profiles = []

    options = ["— Manual entry —"] + [f"{p.name}  ·  {p.environment}" for p in profiles]
    choice = st.sidebar.selectbox("Run queries against", options, key="active_conn_choice")

    if choice == "— Manual entry —":
        return _draw_manual_connection()

    profile = profiles[options.index(choice) - 1]
    st.sidebar.caption(
        f"{profile.username}@{profile.host}:{profile.port} / {profile.service_name or profile.sid}"
    )
    try:
        resolved = store.resolve(profile.id)
    except SecretConfigError as e:
        # Intentional operator guidance — verbatim + a logged reference (ITM-017).
        st.sidebar.error(f"{e} (ref: {log_error_for_ui(e, context='ui.secret_config')})")
        return None
    if resolved is None:
        st.sidebar.error("Selected profile could not be resolved.")
        return None

    cfg_obj = _resolved_to_cfg(resolved)
    if st.sidebar.button("Test connection", width="stretch"):
        ok, msg = _try_connect(cfg_obj)
        (st.sidebar.success if ok else st.sidebar.error)(msg)
    return cfg_obj


# --------------------------------------------------------------------------- #
# Connections tab: manage saved profiles
# --------------------------------------------------------------------------- #
def draw_connections(store: JsonFileProfileStore):
    st.header("Connections")
    st.write("Save named Oracle connections. Passwords are encrypted at rest and never displayed.")

    with st.form("add_profile", clear_on_submit=False):
        st.subheader("Add a connection profile")
        c1, c2 = st.columns(2)
        with c1:
            name = st.text_input("Profile name", key="profile_name")
            host = st.text_input("Host", key="profile_host")
            port = st.number_input("Port", min_value=1, max_value=65535, value=1521, key="profile_port")
            environment = st.selectbox("Environment", ["DEV", "TEST", "PROD"], key="profile_env")
        with c2:
            service_name = st.text_input("Service name (preferred)", key="profile_service")
            sid = st.text_input("SID (optional)", key="profile_sid")
            username = st.text_input("Username", key="profile_username")
            password = st.text_input("Password", type="password", key="profile_password")
        submitted = st.form_submit_button("Add profile")

    if submitted:
        try:
            created = store.create(
                ProfileCreate(
                    name=name,
                    host=host,
                    port=int(port),
                    service_name=service_name or None,
                    sid=sid or None,
                    username=username,
                    password=password,
                    environment=environment,
                )
            )
            st.success(f"Profile '{created.name}' added.")
        except SecretConfigError as e:
            st.error(f"{e} (ref: {log_error_for_ui(e, context='ui.secret_config')})")
        except Exception as e:  # noqa: BLE001 - validation / duplicate name
            st.error(f"Could not add profile: {e}")

    st.subheader("Saved profiles")
    profiles: List[ProfilePublic] = store.list()
    if not profiles:
        st.info("No profiles yet. Add one above.")
        return

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "name": p.name,
                    "env": p.environment,
                    "host": p.host,
                    "port": p.port,
                    "service/sid": p.service_name or p.sid,
                    "username": p.username,
                }
                for p in profiles
            ]
        ),
        width="stretch",
        hide_index=True,
    )

    labels = {f"{p.name}  ·  {p.environment}": p for p in profiles}
    selected = labels[st.selectbox("Select a profile", list(labels.keys()), key="conn_select_profile")]
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Test selected", width="stretch", key="conn_test_selected"):
            try:
                resolved = store.resolve(selected.id)
                ok, msg = _try_connect(_resolved_to_cfg(resolved))
                (st.success if ok else st.error)(msg)
            except SecretConfigError as e:
                st.error(f"{e} (ref: {log_error_for_ui(e, context='ui.secret_config')})")
    with col2:
        if st.button("Delete selected", width="stretch", key="conn_delete_selected"):
            store.delete(selected.id)
            st.success(f"Deleted '{selected.name}'.")
            st.rerun()


# --------------------------------------------------------------------------- #
# Settings tab: per-user LLM configuration (session-only)
# --------------------------------------------------------------------------- #
def draw_settings():
    st.header("Settings")
    st.subheader("LLM provider (per user)")
    st.caption(
        "Choose how natural-language questions are turned into SQL. Your API key "
        "is held only in this session and is never written to disk. Leave the "
        "provider on 'Server default' to use the key configured on the server."
    )

    current: Optional[LLMConfig] = st.session_state.llm_config
    provider_labels = ["Server default (env)", "Groq", "OpenAI"]
    if current is None:
        idx = 0
    elif (current.provider or "").lower() == "groq":
        idx = 1
    else:
        idx = 2

    provider = st.selectbox("Provider", provider_labels, index=idx)
    model_placeholder = (
        DEFAULT_GROQ_MODEL if provider == "Groq" else DEFAULT_OPENAI_MODEL if provider == "OpenAI" else ""
    )
    model = st.text_input(
        "Model (optional)",
        value=(current.model if current and current.model else ""),
        placeholder=model_placeholder,
    )
    api_key = st.text_input(
        "API key (optional — leave blank to use the server's env key for this provider)",
        type="password",
    )

    if st.button("Save LLM settings"):
        if provider.startswith("Server default"):
            st.session_state.llm_config = None
            st.success("Using the server's default LLM configuration.")
        else:
            prov = "groq" if provider == "Groq" else "openai"
            st.session_state.llm_config = LLMConfig(
                provider=prov,
                model=model or None,
                api_key=api_key or None,
            )
            st.success(f"Saved {provider} settings for this session.")

    cfg = st.session_state.llm_config
    if cfg is None:
        st.info("Active: server default (environment configuration).")
    else:
        key_state = "your session key" if cfg.api_key else "server env key"
        st.info(
            f"Active: {cfg.provider} · model = {cfg.model or 'provider default'} · key = {key_state}"
        )


# --------------------------------------------------------------------------- #
# Schema upload & explorer (unchanged behaviour)
# --------------------------------------------------------------------------- #
def _columns_df(cols: List[ColumnDefinition]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "table": c.table_name,
                "column": c.column_name,
                "type": c.data_type or "",
                "PK": "Y" if c.is_primary_key else "",
                "FK": "Y" if c.is_foreign_key else "",
                "references": (
                    f"{c.references_table}.{c.references_column}"
                    if c.references_table and c.references_column
                    else ""
                ),
            }
            for c in cols
        ]
    )


def draw_schema_sources(conn_cfg: Optional[OracleConnectionConfig]):
    st.header("Schema Sources")
    st.caption(
        "Load a data dictionary by uploading metadata, introspecting a live connection, "
        "or loading a saved schema. The active schema powers NL→SQL and the Data Dictionary."
    )

    # --- Upload --------------------------------------------------------- #
    with st.expander("Upload metadata (CSV/Excel)", expanded=st.session_state.schema is None):
        st.write(
            "Columns: table_name, column_name, data_type, is_primary_key, is_foreign_key, "
            "references_table, references_column."
        )
        schema_file = st.file_uploader("Schema file (CSV/Excel)", type=["csv", "xlsx", "xls"])
        rel_file = st.file_uploader(
            "Relationships (optional, CSV/Excel)", type=["csv", "xlsx", "xls"], key="rel"
        )
        if st.button("Parse schema", key="schema_parse"):
            if not schema_file:
                st.error("Please upload a schema file first.")
            else:
                try:
                    schema = parse_schema_dataframe(read_tabular_file(schema_file.read(), schema_file.name))
                    if rel_file is not None:
                        rels = parse_relationships_dataframe(read_tabular_file(rel_file.read(), rel_file.name))
                        schema = attach_relationships(schema, rels)
                    st.session_state.schema = schema
                    st.session_state.schema_source = "upload"
                    st.success(f"Schema parsed: {len(schema.tables)} tables loaded.")
                except Exception as e:  # noqa: BLE001
                    st.error(f"Failed to parse schema: {e}")

    # --- Introspect ----------------------------------------------------- #
    with st.expander("Introspect from connection (read-only)"):
        st.caption(
            "Builds the dictionary from Oracle's ALL_* views via SELECT-only queries, "
            "under your read-only account. Scope it with an owner and a name filter."
        )
        default_owner = (conn_cfg.username.upper() if conn_cfg and conn_cfg.username else "")
        ic1, ic2 = st.columns(2)
        with ic1:
            owner = st.text_input("Owner / schema", value=default_owner, key="introspect_owner")
        with ic2:
            table_like = st.text_input("Table name filter (LIKE)", value="%", key="introspect_like")
        if st.button("Introspect", key="introspect_btn"):
            if not conn_cfg:
                st.warning("Choose a connection in the sidebar first.")
            elif not owner.strip():
                st.error("Provide an owner/schema.")
            else:
                try:
                    result = introspect_schema(OracleClient(conn_cfg), owner=owner, table_like=table_like)
                    st.session_state.schema = result.schema
                    st.session_state.schema_source = "introspection"
                    msg = f"Introspected {len(result.schema.tables)} tables for {owner.upper()}."
                    (st.warning if result.truncated else st.success)(
                        msg + (" Results truncated by limits — narrow the filter." if result.truncated else "")
                    )
                    for w in result.warnings:
                        st.info(w)
                except ValueError as e:
                    # Safe, intentional validation message — show verbatim.
                    st.error(str(e))
                except Exception as e:  # noqa: BLE001 - driver error: sanitize (ITM-015)
                    error_id, msg = sanitize_db_error_for_ui(e, context="ui-introspect")
                    st.error(f"Introspection failed — {msg} (ref: {error_id})")

    # --- Library -------------------------------------------------------- #
    with st.expander("Library (saved schemas)"):
        store = get_schema_store()
        c1, c2 = st.columns([2, 1])
        with c1:
            save_name = st.text_input("Save current schema as", key="schema_save_name")
        with c2:
            if st.button("Save to library", key="schema_save_btn", width="stretch"):
                if not st.session_state.schema:
                    st.warning("No active schema to save.")
                elif not save_name.strip():
                    st.error("Provide a name.")
                else:
                    try:
                        store.create(
                            save_name,
                            schema_to_dict(st.session_state.schema),
                            source=st.session_state.schema_source,
                        )
                        st.success(f"Saved '{save_name}'.")
                    except Exception as e:  # noqa: BLE001
                        st.error(str(e))

        summaries = store.list()
        if summaries:
            labels = {f"{s.name}  ·  {s.table_count} tables  ·  {s.source}": s for s in summaries}
            chosen = st.selectbox("Saved schemas", list(labels.keys()), key="schema_load_select")
            lc1, lc2 = st.columns(2)
            with lc1:
                if st.button("Load", key="schema_load_btn", width="stretch"):
                    record = store.get(labels[chosen].id)
                    if record:
                        try:
                            st.session_state.schema = schema_from_dict(record.definition)
                            st.session_state.schema_source = record.source
                            st.success(f"Loaded '{record.name}'.")
                            st.rerun()
                        except Exception as e:  # noqa: BLE001 - never crash on a bad stored blob
                            st.error(f"Could not load schema: {e}")
            with lc2:
                if st.button("Delete", key="schema_delete_btn", width="stretch"):
                    store.delete(labels[chosen].id)
                    st.success("Deleted.")
                    st.rerun()
        else:
            st.info("No saved schemas yet.")

    if st.session_state.schema:
        st.success(f"Active schema: {len(st.session_state.schema.tables)} tables ({st.session_state.schema_source}).")


def draw_data_dictionary(schema: Schema):
    st.header("Data Dictionary")

    # --- EBS packs (Phase 7, reference) -------------------------------- #
    with st.expander("EBS Packs — module metadata + glossary (reference)"):
        st.caption("Curated EBS table descriptions and business-term glossary — review before use.")
        pmod = st.selectbox("EBS module", [p.module for p in list_packs()], key="dict_ebs_module")
        pack = get_pack(pmod)
        if pack:
            st.markdown(f"**{pack.name} — tables**")
            st.dataframe(
                pd.DataFrame(
                    [{"table": t.table, "description": t.description, "key columns": ", ".join(t.key_columns)}
                     for t in pack.tables]
                ),
                width="stretch", hide_index=True,
            )
            st.markdown("**Glossary**")
            st.dataframe(
                pd.DataFrame(
                    [{"term": g.term, "maps to": g.table + (f".{g.column}" if g.column else ""), "note": g.note or ""}
                     for g in pack.glossary]
                ),
                width="stretch", hide_index=True,
            )

    # --- Search / filter ----------------------------------------------- #
    st.subheader("Search")
    s1, s2, s3, s4 = st.columns([3, 2, 1, 1])
    with s1:
        query = st.text_input("Table or column contains", key="dict_search")
    with s2:
        dtype = st.text_input("Data type contains", key="dict_dtype")
    with s3:
        pk_only = st.checkbox("PK only", key="dict_pk")
    with s4:
        fk_only = st.checkbox("FK only", key="dict_fk")

    matches = find_columns(
        schema,
        query,
        data_type=dtype or None,
        pk=True if pk_only else None,
        fk=True if fk_only else None,
    )
    st.caption(f"{len(matches)} column(s) match.")
    if matches:
        st.dataframe(_columns_df(matches), width="stretch", hide_index=True)

    # --- Table detail + relationship navigation ------------------------ #
    st.subheader("Table detail")
    table = st.selectbox("Select a table", options=schema.list_tables(), key="dict_table")
    if table:
        st.dataframe(_columns_df(table_detail(schema, table)), width="stretch", hide_index=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**References out** (this table's foreign keys)")
            out = references_out(schema, table)
            if out:
                st.dataframe(
                    pd.DataFrame(out, columns=["column", "to_table", "to_column"]),
                    width="stretch", hide_index=True,
                )
            else:
                st.caption("None.")
        with c2:
            st.markdown("**Where used** (tables referencing this one)")
            inbound = referenced_by(schema, table)
            if inbound:
                st.dataframe(
                    pd.DataFrame(inbound, columns=["from_table", "from_column", "to_column"]),
                    width="stretch", hide_index=True,
                )
            else:
                st.caption("None.")

    # --- Export --------------------------------------------------------- #
    st.subheader("Export dictionary")
    all_cols = [c for t in schema.tables.values() for c in t.columns]
    df = _columns_df(all_cols)
    e1, e2, e3 = st.columns(3)
    with e1:
        st.download_button("CSV", data=dataframe_to_csv_bytes(df), file_name="data_dictionary.csv", mime="text/csv")
    with e2:
        st.download_button(
            "Excel", data=dataframe_to_excel_bytes(df, sheet_name="Dictionary"),
            file_name="data_dictionary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    with e3:
        st.download_button(
            "Markdown", data=schema.to_compact_markdown().encode("utf-8"),
            file_name="data_dictionary.md", mime="text/markdown",
        )


# --------------------------------------------------------------------------- #
# Query builder
# --------------------------------------------------------------------------- #
def _run_and_display(client: OracleClient, sql: str, binds: Optional[Dict[str, object]] = None):
    try:
        result = client.run_select(sql, binds=binds)
        df = pd.DataFrame(result.rows, columns=result.columns)
        st.session_state.last_results = df
        msg = f"Query OK in {result.elapsed_seconds:.2f}s, {result.row_count} rows"
        if result.truncated:
            st.warning(msg + " — result truncated by safety limits.")
        else:
            st.success(msg)
        st.dataframe(df, width="stretch")
        e1, e2 = st.columns(2)
        with e1:
            st.download_button("Download CSV", data=dataframe_to_csv_bytes(df), file_name="results.csv", mime="text/csv")
        with e2:
            st.download_button(
                "Download Excel",
                data=dataframe_to_excel_bytes(df),
                file_name="results.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    except SqlSafetyError as e:
        # Safety rejection reason is user-actionable — show verbatim.
        st.error(f"Query rejected: {e}")
    except Exception as e:  # noqa: BLE001 - driver error: sanitize (ITM-015)
        error_id, msg = sanitize_db_error_for_ui(e, context="ui-execute")
        st.error(f"{msg} (ref: {error_id})")


def _append_recipient(addr: str) -> None:
    """Add a quick-pick address to the To field (set before the widget is drawn)."""
    current = (st.session_state.get("email_to") or "").strip()
    parts = [p.strip() for p in current.split(",") if p.strip()]
    if addr not in parts:
        parts.append(addr)
    st.session_state.email_to = ", ".join(parts)


def _render_email_action(df: Optional[pd.DataFrame]) -> None:
    """Follow-up action (Phase 8): email the last result with the output attached.

    Opt-in — only shown when SMTP is configured (``email_enabled``). Rendered from
    ``last_results`` so the form survives Streamlit reruns (type recipient → send).
    """
    if df is None or not email_enabled():
        return
    with st.expander("✉️ Send as email (follow-up action)", expanded=False):
        st.caption(f"Email the last result — {len(df)} rows × {len(df.columns)} columns.")
        candidates = detect_recipient_candidates(df)
        if candidates:
            st.caption("Recipients found in the results — click to add:")
            chip_cols = st.columns(min(4, len(candidates)))
            for i, addr in enumerate(candidates):
                with chip_cols[i % len(chip_cols)]:
                    # Runs before the To input below, so updating its state is allowed.
                    if st.button(f"+ {addr}", key=f"qp_{addr}"):
                        _append_recipient(addr)
        st.text_input("To (comma-separated)", key="email_to")
        st.text_input("Cc (optional)", key="email_cc")
        st.text_input(
            "Subject",
            value=f"Report results — {len(df)} rows — {pd.Timestamp.now():%Y-%m-%d}",
            key="email_subject",
        )
        st.text_area("Message", value="Please find the report attached.", key="email_body", height=100)
        fmt = st.radio("Attachment", ["CSV", "Excel"], horizontal=True, key="email_fmt")
        if st.button("Send email", type="primary", key="email_send"):
            result = send_report_email(
                to=st.session_state.get("email_to", ""),
                cc=st.session_state.get("email_cc", ""),
                subject=st.session_state.get("email_subject", ""),
                body=st.session_state.get("email_body", ""),
                df=df,
                attachment_format="excel" if fmt == "Excel" else "csv",
            )
            if result.ok:
                st.success(result.message)
            elif result.kind == "rejected":
                st.warning(result.message)
            else:
                st.error(f"{result.message} (ref: {result.error_id})")


def draw_query_builder(conn_cfg: Optional[OracleConnectionConfig], schema: Optional[Schema]):
    st.header("Build & Run Reports")
    if not conn_cfg:
        st.warning("Choose a saved profile or fill in a manual connection in the sidebar to run queries.")
    mode = st.radio("Query mode", ["Natural Language", "Raw SQL"], horizontal=True)
    client = OracleClient(conn_cfg) if conn_cfg else None

    if mode == "Natural Language":
        prompt = st.text_area("What do you want to see?", placeholder="Show me total AP invoices by vendor for last quarter")
        ebs_mods = st.multiselect(
            "EBS module context (optional)",
            ["GL", "AP", "AR", "PO", "OM"],
            key="nl_ebs_modules",
            help="Adds curated EBS table descriptions + glossary so the model can map business terms to EBS tables.",
        )
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Generate SQL"):
                if not schema:
                    st.error("Upload schema first.")
                else:
                    try:
                        result = generate_sql_from_nl(
                            prompt, schema, llm=st.session_state.llm_config, ebs_modules=ebs_mods or None
                        )
                        st.session_state.generated_sql = result.sql
                        st.session_state.nl_explanation = result.explanation
                        st.session_state.nl_confidence = (
                            {"level": result.confidence.level, "reasons": result.confidence.reasons}
                            if result.confidence
                            else None
                        )
                        st.success("SQL generated. Review it below before running.")
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Failed to generate SQL: {e}")
        with col2:
            run_clicked = st.button("Run SQL")

        sql_box_val = st.text_area("Generated SQL (editable)", value=st.session_state.generated_sql, height=200)
        st.session_state.generated_sql = sql_box_val

        conf = st.session_state.nl_confidence
        if conf:
            badge = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(conf["level"], "⚪")
            reasons = f" — {'; '.join(conf['reasons'])}" if conf.get("reasons") else ""
            st.caption(f"Confidence: {badge} {conf['level']}{reasons}")
        if st.session_state.nl_explanation:
            with st.expander("Explanation", expanded=True):
                st.write(st.session_state.nl_explanation)

        if run_clicked and client and sql_box_val.strip():
            _run_and_display(client, sql_box_val)

    else:  # Raw SQL
        sql = st.text_area("SQL", placeholder="SELECT * FROM some_table WHERE ROWNUM <= 100")
        if st.button("Run SQL (SELECT only)"):
            if not client:
                st.error("Configure a connection first.")
            elif sql.strip():
                _run_and_display(client, sql)

    _render_email_action(st.session_state.get("last_results"))


def _profile_options(store: JsonFileProfileStore) -> Dict[str, Optional[str]]:
    """Map a display label → profile id, with a leading '— none —' → None."""
    labels: Dict[str, Optional[str]] = {"— none —": None}
    for p in store.list():
        labels[f"{p.name}  ·  {p.environment}"] = p.id
    return labels


def draw_reports(conn_cfg: Optional[OracleConnectionConfig]):
    st.header("Reports")
    rstore = get_report_store()
    pstore = get_store()
    reports = rstore.list()

    # --- Run a saved report ------------------------------------------------ #
    st.subheader("Run a saved report")
    if not reports:
        st.info("No saved reports yet. Save one below, or from the Templates section.")
    else:
        names = {r.name: r for r in reports}
        report = names[st.selectbox("Select a report", list(names.keys()), key="rep_run_select")]
        if report.description:
            st.caption(report.description)
        st.code(report.sql, language="sql")

        raw_values: Dict[str, object] = {}
        if report.parameters:
            st.markdown("**Parameters** (* required)")
            cols = st.columns(min(3, len(report.parameters)))
            for i, p in enumerate(report.parameters):
                with cols[i % len(cols)]:
                    label = (p.label or p.name) + (" *" if p.required else "")
                    raw_values[p.name] = st.text_input(
                        label,
                        value="" if p.default is None else str(p.default),
                        key=f"repparam_{report.id}_{p.name}",
                        help=f"type: {p.type}",
                    )

        prof_labels = _profile_options(pstore)
        bound_label = next(
            (lbl for lbl, pid in prof_labels.items() if pid == report.default_profile_id),
            "— none —",
        )
        target_choice = st.selectbox(
            "Run against profile (or use the sidebar connection)",
            list(prof_labels.keys()),
            index=list(prof_labels.keys()).index(bound_label),
            key=f"rep_target_{report.id}",
        )
        target_profile_id = prof_labels[target_choice]

        if st.button("Run report", key=f"rep_run_{report.id}"):
            provided = {k: v for k, v in raw_values.items() if v != ""}
            try:
                binds = coerce_report_binds(report.parameters, provided)
            except ValueError as e:
                st.error(str(e))
            else:
                client: Optional[OracleClient] = None
                if target_profile_id:
                    try:
                        resolved = pstore.resolve(target_profile_id)
                        client = OracleClient(_resolved_to_cfg(resolved)) if resolved else None
                    except SecretConfigError as e:
                        st.error(f"{e} (ref: {log_error_for_ui(e, context='ui.secret_config')})")
                elif conn_cfg:
                    client = OracleClient(conn_cfg)
                if client is None:
                    st.warning(
                        "No connection target. Bind a profile, pick one above, or set the "
                        "sidebar connection."
                    )
                else:
                    _run_and_display(client, report.sql, binds=binds)

    _render_email_action(st.session_state.get("last_results"))

    # --- Save / manage ----------------------------------------------------- #
    st.markdown("---")
    st.subheader("Save / manage reports")
    current_sql = st.session_state.generated_sql or ""
    with st.expander("Save current SQL as a report", expanded=not reports):
        if not current_sql.strip():
            st.info("Generate or type SQL in the Query Builder first, or load a template.")
        else:
            st.code(current_sql, language="sql")
            name = st.text_input("Report name", key="rep_save_name")
            description = st.text_input("Description (optional)", key="rep_save_desc")
            params: List[ReportParam] = []
            for pname in _detect_params(current_sql):
                c1, c2, c3 = st.columns([1, 1, 2])
                with c1:
                    ptype = st.selectbox(f":{pname} type", ["string", "number", "date"], key=f"savep_type_{pname}")
                with c2:
                    preq = st.checkbox("required", value=True, key=f"savep_req_{pname}")
                with c3:
                    pdef = st.text_input("default", key=f"savep_def_{pname}")
                params.append(ReportParam(name=pname, type=ptype, required=preq, default=(pdef or None)))
            bind_label = st.selectbox("Bind to profile (optional)", list(_profile_options(pstore).keys()), key="rep_save_bind")
            if st.button("Save report", key="rep_save_btn"):
                if not name.strip():
                    st.error("Provide a report name.")
                else:
                    try:
                        rstore.create(
                            ReportCreate(
                                name=name,
                                description=description,
                                sql=current_sql,
                                parameters=params,
                                default_profile_id=_profile_options(pstore)[bind_label],
                            )
                        )
                        st.success(f"Saved report '{name}'.")
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

    if reports:
        del_choice = st.selectbox("Delete a report", ["—"] + [r.name for r in reports], key="rep_del_select")
        if st.button("Delete report", key="rep_del_btn") and del_choice != "—":
            rid = next(r.id for r in reports if r.name == del_choice)
            rstore.delete(rid)
            st.success(f"Deleted '{del_choice}'.")
            st.rerun()


def draw_templates():
    st.header("Templates")
    st.caption(
        "Curated standard-EBS starter queries. They assume a standard EBS schema — "
        "review and adjust before running. Nothing runs automatically."
    )
    templates = list_templates()
    module = st.selectbox("Module", sorted({t.module for t in templates}), key="tpl_module")
    in_mod = [t for t in templates if t.module == module]
    tpl = next(t for t in in_mod if t.name == st.selectbox("Template", [t.name for t in in_mod], key="tpl_select"))

    st.caption(tpl.description)
    st.code(tpl.sql, language="sql")
    if tpl.parameters:
        st.markdown("**Parameters:** " + ", ".join(f"`:{p.name}` ({p.type})" for p in tpl.parameters))

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Load into Query Builder", key="tpl_load"):
            st.session_state.generated_sql = tpl.sql
            st.session_state.nl_explanation = None
            st.session_state.nl_confidence = None
            st.success("Loaded into Query Builder — switch to it from the left nav to run.")
    with c2:
        save_name = st.text_input("Save as report — name", value=tpl.name, key="tpl_save_name")
        if st.button("Save as report", key="tpl_save"):
            try:
                get_report_store().create(
                    ReportCreate(
                        name=save_name,
                        description=tpl.description,
                        sql=tpl.sql,
                        parameters=tpl.parameters,
                        template_id=tpl.id,
                    )
                )
                st.success(f"Saved report '{save_name}'.")
            except ValueError as e:
                st.error(str(e))


# --------------------------------------------------------------------------- #
# Layout — left-nav (sidebar) over a single app with shared session state
# --------------------------------------------------------------------------- #
SECTIONS = [
    "Connections",
    "Schema Sources",
    "Data Dictionary",
    "Query Builder",
    "Reports",
    "Templates",
    "Settings",
]

st.sidebar.title("Ask Oracle Reports")
section = st.sidebar.radio("Navigate", SECTIONS, key="nav")
st.sidebar.markdown("---")
conn_cfg = draw_sidebar_connection()

if section == "Connections":
    draw_connections(get_store())
elif section == "Schema Sources":
    draw_schema_sources(conn_cfg)
elif section == "Data Dictionary":
    if st.session_state.schema:
        draw_data_dictionary(st.session_state.schema)
    else:
        st.info("Load a schema in **Schema Sources** first (upload, introspect, or load a saved one).")
elif section == "Query Builder":
    draw_query_builder(conn_cfg, st.session_state.schema)
elif section == "Reports":
    draw_reports(conn_cfg)
elif section == "Templates":
    draw_templates()
elif section == "Settings":
    draw_settings()
