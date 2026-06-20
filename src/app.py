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
if "selected_report_id" not in st.session_state:
    st.session_state.selected_report_id = None


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
        current_schema=getattr(resolved, "current_schema", None),
    )


def _try_connect(cfg: OracleConnectionConfig) -> Tuple[bool, str]:
    try:
        result = OracleClient(cfg).run_select("SELECT 1 FROM DUAL")
        return True, f"Connected successfully in {result.elapsed_seconds:.2f}s"
    except Exception as e:  # noqa: BLE001 - driver/connection error: sanitize (ITM-015)
        error_id, msg = sanitize_db_error_for_ui(e, context="ui-test-connection")
        return False, f"Connection failed — {msg} (ref: {error_id})"


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


# --------------------------------------------------------------------------- #
# Email — @st.dialog keeps it off the page scroll entirely (ITM-023)
# --------------------------------------------------------------------------- #
@st.dialog("Send as Email", width="large")
def _email_dialog(df: pd.DataFrame) -> None:
    st.caption(f"{len(df)} rows × {len(df.columns)} columns — sent as attachment")
    candidates = detect_recipient_candidates(df)
    if candidates:
        st.caption("Recipients found in results — click to add:")
        chip_cols = st.columns(min(4, len(candidates)))
        for i, addr in enumerate(candidates):
            with chip_cols[i % len(chip_cols)]:
                if st.button(f"+ {addr}", key=f"dlg_qp_{addr}"):
                    current = (st.session_state.get("dlg_email_to") or "").strip()
                    parts = [p.strip() for p in current.split(",") if p.strip()]
                    if addr not in parts:
                        parts.append(addr)
                    st.session_state.dlg_email_to = ", ".join(parts)

    c1, c2 = st.columns(2)
    with c1:
        st.text_input("To (comma-separated)", key="dlg_email_to")
    with c2:
        st.text_input("Cc (optional)", key="dlg_email_cc")
    st.text_input(
        "Subject",
        value=f"Report results — {len(df)} rows — {pd.Timestamp.now():%Y-%m-%d}",
        key="dlg_email_subject",
    )
    st.text_area("Message", value="Please find the report attached.", key="dlg_email_body", height=80)
    fmt = st.radio("Attachment format", ["CSV", "Excel"], horizontal=True, key="dlg_email_fmt")

    btn_l, btn_r = st.columns(2)
    with btn_l:
        if st.button("Cancel", use_container_width=True):
            st.rerun()
    with btn_r:
        if st.button("Send", type="primary", use_container_width=True):
            result = send_report_email(
                to=st.session_state.get("dlg_email_to", ""),
                cc=st.session_state.get("dlg_email_cc", ""),
                subject=st.session_state.get("dlg_email_subject", ""),
                body=st.session_state.get("dlg_email_body", ""),
                df=df,
                attachment_format="excel" if fmt == "Excel" else "csv",
            )
            if result.ok:
                st.success(result.message)
                for _k in ("dlg_email_to", "dlg_email_cc", "dlg_email_subject", "dlg_email_body"):
                    st.session_state.pop(_k, None)
                st.rerun()
            elif result.kind == "rejected":
                st.warning(result.message)
            else:
                st.error(f"{result.message} (ref: {result.error_id})")


# --------------------------------------------------------------------------- #
# Query execution — stores result in session_state; caller renders it
# --------------------------------------------------------------------------- #
def _execute_query(
    client: OracleClient, sql: str, binds: Optional[Dict[str, object]] = None
) -> bool:
    """Run sql, store DataFrame in session_state.last_results. Returns True on success."""
    try:
        result = client.run_select(sql, binds=binds)
        df = pd.DataFrame(result.rows, columns=result.columns)
        st.session_state.last_results = df
        msg = f"✓ {result.row_count} rows in {result.elapsed_seconds:.2f}s"
        if result.truncated:
            st.warning(msg + " — truncated by safety limits.")
        else:
            st.success(msg)
        return True
    except SqlSafetyError as e:
        # Safety rejection reason is user-actionable — show verbatim.
        st.error(f"Query rejected: {e}")
        st.session_state.last_results = None
        return False
    except Exception as e:  # noqa: BLE001 - driver error: sanitize (ITM-015)
        error_id, msg = sanitize_db_error_for_ui(e, context="ui-execute")
        st.error(f"{msg} (ref: {error_id})")
        st.session_state.last_results = None
        return False


def _render_results(df: pd.DataFrame, email_key: str = "email_btn") -> None:
    """Render results dataframe, download buttons, and email trigger."""
    st.caption(f"{len(df)} rows · {len(df.columns)} columns")
    st.dataframe(df, use_container_width=True, hide_index=True, height=220)
    dl1, dl2, dl3 = st.columns(3)
    with dl1:
        st.download_button(
            "↓ CSV", data=dataframe_to_csv_bytes(df),
            file_name="results.csv", mime="text/csv",
            use_container_width=True, key=f"{email_key}_csv",
        )
    with dl2:
        st.download_button(
            "↓ Excel", data=dataframe_to_excel_bytes(df),
            file_name="results.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True, key=f"{email_key}_xlsx",
        )
    with dl3:
        if email_enabled():
            if st.button("✉ Email", use_container_width=True, key=email_key):
                _email_dialog(df)


# --------------------------------------------------------------------------- #
# Sidebar: compact nav + active connection selector
# --------------------------------------------------------------------------- #
def draw_sidebar_connection() -> Optional[OracleConnectionConfig]:
    store = get_store()
    try:
        profiles = store.list()
    except Exception as e:  # noqa: BLE001
        st.sidebar.error(f"Could not load profiles: {e}")
        profiles = []

    options = ["— Manual entry —"] + [f"{p.name}  ·  {p.environment}" for p in profiles]
    choice = st.sidebar.selectbox(
        "Connection", options, key="active_conn_choice", label_visibility="collapsed"
    )

    if choice != "— Manual entry —":
        profile = profiles[options.index(choice) - 1]
        st.sidebar.caption(f"🟢 {profile.name} · {profile.host}")
        try:
            resolved = store.resolve(profile.id)
        except SecretConfigError as e:
            st.sidebar.error(f"{e} (ref: {log_error_for_ui(e, context='ui.secret_config')})")
            return None
        if resolved is None:
            st.sidebar.error("Profile could not be resolved.")
            return None
        cfg_obj = _resolved_to_cfg(resolved)
        if st.sidebar.button("Test connection", use_container_width=True):
            ok, msg = _try_connect(cfg_obj)
            (st.sidebar.success if ok else st.sidebar.error)(msg)
        return cfg_obj

    # Manual entry in a collapsed expander so the sidebar never scrolls by default.
    with st.sidebar.expander("Manual entry (session only)"):
        cfg = st.session_state.conn_config
        host = st.text_input("Host", value=str(cfg.get("host", "")), key="man_host")
        port = st.number_input(
            "Port", min_value=1, max_value=65535, value=int(cfg.get("port", 1521)), key="man_port"
        )
        service_name = st.text_input(
            "Service name", value=str(cfg.get("service_name") or ""), key="man_svc"
        )
        sid = st.text_input("SID (optional)", value=str(cfg.get("sid") or ""), key="man_sid")
        username = st.text_input("Username", value=str(cfg.get("username", "")), key="man_user")
        password = st.text_input(
            "Password", value=str(cfg.get("password", "")), type="password", key="man_pwd"
        )
        current_schema = st.text_input(
            "Default schema",
            value=str(cfg.get("current_schema") or ""),
            key="man_schema",
            help="Runs ALTER SESSION SET CURRENT_SCHEMA on connect (e.g. AOR_DEMO).",
        )
        cfg_obj: Optional[OracleConnectionConfig] = None
        if host and username and password and (service_name or sid):
            cfg_obj = OracleConnectionConfig(
                host=host, port=int(port),
                service_name=service_name or None, sid=sid or None,
                username=username, password=password,
                current_schema=current_schema or None,
            )
        if st.button("Test", key="man_test", use_container_width=True):
            if cfg_obj:
                ok, msg = _try_connect(cfg_obj)
                (st.success if ok else st.error)(msg)
            else:
                st.error("Fill host, username, password, and service name or SID.")
    return cfg_obj


# --------------------------------------------------------------------------- #
# Connections — 2-panel: add form left · profile list right
# --------------------------------------------------------------------------- #
def draw_connections(store: JsonFileProfileStore):
    left, right = st.columns([1, 1])

    with left:
        st.markdown("##### Add a profile")
        st.caption("Passwords are encrypted at rest and never displayed.")
        with st.form("add_profile", clear_on_submit=False):
            name = st.text_input("Profile name", key="profile_name")
            c1, c2 = st.columns(2)
            with c1:
                host = st.text_input("Host", key="profile_host")
                port = st.number_input(
                    "Port", min_value=1, max_value=65535, value=1521, key="profile_port"
                )
                environment = st.selectbox("Environment", ["DEV", "TEST", "PROD"], key="profile_env")
            with c2:
                service_name = st.text_input("Service name", key="profile_service")
                sid = st.text_input("SID (optional)", key="profile_sid")
                username = st.text_input("Username", key="profile_username")
            password = st.text_input("Password", type="password", key="profile_password")
            schema = st.text_input(
                "Default schema (optional)", key="profile_schema",
                help="Runs ALTER SESSION SET CURRENT_SCHEMA on connect (e.g. AOR_DEMO).",
            )
            submitted = st.form_submit_button(
                "Add profile", use_container_width=True, type="primary"
            )

        if submitted:
            try:
                created = store.create(
                    ProfileCreate(
                        name=name, host=host, port=int(port),
                        service_name=service_name or None, sid=sid or None,
                        current_schema=schema or None, username=username,
                        password=password, environment=environment,
                    )
                )
                st.success(f"Profile '{created.name}' added.")
            except SecretConfigError as e:
                st.error(f"{e} (ref: {log_error_for_ui(e, context='ui.secret_config')})")
            except Exception as e:  # noqa: BLE001
                st.error(f"Could not add profile: {e}")

    with right:
        profiles: List[ProfilePublic] = store.list()
        st.markdown(f"##### Saved profiles ({len(profiles)})")
        if not profiles:
            st.info("No profiles yet. Add one on the left.")
        else:
            with st.container(height=260):
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
                    use_container_width=True, hide_index=True,
                )
            labels = {f"{p.name}  ·  {p.environment}": p for p in profiles}
            selected = labels[
                st.selectbox(
                    "Select profile",
                    list(labels.keys()),
                    key="conn_select_profile",
                    label_visibility="collapsed",
                )
            ]
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Test selected", use_container_width=True, key="conn_test_selected"):
                    try:
                        resolved = store.resolve(selected.id)
                        ok, msg = _try_connect(_resolved_to_cfg(resolved))
                        (st.success if ok else st.error)(msg)
                    except SecretConfigError as e:
                        st.error(f"{e} (ref: {log_error_for_ui(e, context='ui.secret_config')})")
            with c2:
                if st.button("Delete selected", use_container_width=True, key="conn_delete_selected"):
                    store.delete(selected.id)
                    st.success(f"Deleted '{selected.name}'.")
                    st.rerun()


# --------------------------------------------------------------------------- #
# Schema Sources — 2-panel: source actions left · browser/library right
# --------------------------------------------------------------------------- #
def draw_schema_sources(conn_cfg: Optional[OracleConnectionConfig]):
    left, right = st.columns([1, 1])

    with left:
        upload_tab, introspect_tab, library_tab = st.tabs(["Upload", "Introspect", "Library"])

        with upload_tab:
            st.caption(
                "Columns: table_name, column_name, data_type, is_primary_key, "
                "is_foreign_key, references_table, references_column."
            )
            schema_file = st.file_uploader(
                "Schema file (CSV/Excel)", type=["csv", "xlsx", "xls"],
                label_visibility="collapsed",
            )
            rel_file = st.file_uploader(
                "Relationships (optional)", type=["csv", "xlsx", "xls"],
                key="rel", label_visibility="collapsed",
            )
            if st.button("Parse and activate schema", type="primary", use_container_width=True):
                if not schema_file:
                    st.error("Upload a schema file first.")
                else:
                    try:
                        schema = parse_schema_dataframe(
                            read_tabular_file(schema_file.read(), schema_file.name)
                        )
                        if rel_file is not None:
                            rels = parse_relationships_dataframe(
                                read_tabular_file(rel_file.read(), rel_file.name)
                            )
                            schema = attach_relationships(schema, rels)
                        st.session_state.schema = schema
                        st.session_state.schema_source = "upload"
                        st.success(f"Schema parsed: {len(schema.tables)} tables loaded.")
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Failed to parse schema: {e}")

        with introspect_tab:
            st.caption(
                "Builds the dictionary from Oracle's ALL_* views via SELECT-only queries, "
                "under your read-only account."
            )
            default_owner = conn_cfg.username.upper() if conn_cfg and conn_cfg.username else ""
            owner = st.text_input("Owner / schema", value=default_owner, key="introspect_owner")
            table_like = st.text_input("Table filter (LIKE)", value="%", key="introspect_like")
            if st.button("Introspect schema", type="primary", use_container_width=True):
                if not conn_cfg:
                    st.warning("Choose a connection in the sidebar first.")
                elif not owner.strip():
                    st.error("Provide an owner/schema.")
                else:
                    try:
                        result = introspect_schema(
                            OracleClient(conn_cfg), owner=owner, table_like=table_like
                        )
                        st.session_state.schema = result.schema
                        st.session_state.schema_source = "introspection"
                        msg = f"Introspected {len(result.schema.tables)} tables for {owner.upper()}."
                        (st.warning if result.truncated else st.success)(
                            msg + (" Truncated — narrow the filter." if result.truncated else "")
                        )
                        for w in result.warnings:
                            st.info(w)
                    except ValueError as e:
                        st.error(str(e))
                    except Exception as e:  # noqa: BLE001
                        error_id, msg = sanitize_db_error_for_ui(e, context="ui-introspect")
                        st.error(f"Introspection failed — {msg} (ref: {error_id})")

        with library_tab:
            schema_store = get_schema_store()
            save_name = st.text_input("Save current schema as", key="schema_save_name")
            if st.button("Save to library", use_container_width=True):
                if not st.session_state.schema:
                    st.warning("No active schema to save.")
                elif not save_name.strip():
                    st.error("Provide a name.")
                else:
                    try:
                        schema_store.create(
                            save_name,
                            schema_to_dict(st.session_state.schema),
                            source=st.session_state.schema_source,
                        )
                        st.success(f"Saved '{save_name}'.")
                    except Exception as e:  # noqa: BLE001
                        st.error(str(e))

            summaries = schema_store.list()
            if summaries:
                st.markdown("---")
                labels = {
                    f"{s.name}  ·  {s.table_count} tables  ·  {s.source}": s
                    for s in summaries
                }
                chosen = st.selectbox(
                    "Saved schemas", list(labels.keys()),
                    key="schema_load_select", label_visibility="collapsed",
                )
                lc1, lc2 = st.columns(2)
                with lc1:
                    if st.button("Load", use_container_width=True, key="schema_load_btn"):
                        record = schema_store.get(labels[chosen].id)
                        if record:
                            try:
                                st.session_state.schema = schema_from_dict(record.definition)
                                st.session_state.schema_source = record.source
                                st.success(f"Loaded '{record.name}'.")
                                st.rerun()
                            except Exception as e:  # noqa: BLE001
                                st.error(f"Could not load schema: {e}")
                with lc2:
                    if st.button("Delete", use_container_width=True, key="schema_delete_btn"):
                        schema_store.delete(labels[chosen].id)
                        st.success("Deleted.")
                        st.rerun()
            else:
                st.info("No saved schemas yet.")

    with right:
        active = st.session_state.schema
        if active:
            st.success(
                f"Active schema: {len(active.tables)} tables ({st.session_state.schema_source})"
            )
            table = st.selectbox(
                "Browse table", options=active.list_tables(),
                key="ss_browse_table", label_visibility="collapsed",
            )
            if table:
                with st.container(height=340):
                    st.dataframe(
                        _columns_df(table_detail(active, table)),
                        use_container_width=True, hide_index=True,
                    )
        else:
            st.info("No schema loaded. Upload a file, introspect from a live connection, or load from the Library.")


# --------------------------------------------------------------------------- #
# Data Dictionary — 2-panel: search/EBS left · table detail right
# --------------------------------------------------------------------------- #
def draw_data_dictionary(schema: Schema):
    left, right = st.columns([1, 1.5])

    with left:
        search_tab, ebs_tab = st.tabs(["Search", "EBS Packs"])

        with search_tab:
            query = st.text_input("Table or column contains", key="dict_search")
            c1, c2 = st.columns([2, 1])
            with c1:
                dtype = st.text_input(
                    "Data type", key="dict_dtype", placeholder="e.g. VARCHAR2"
                )
            with c2:
                pk_only = st.checkbox("PK", key="dict_pk")
                fk_only = st.checkbox("FK", key="dict_fk")

            matches = find_columns(
                schema, query,
                data_type=dtype or None,
                pk=True if pk_only else None,
                fk=True if fk_only else None,
            )
            st.caption(f"{len(matches)} column(s) match")
            with st.container(height=220):
                if matches:
                    st.dataframe(
                        _columns_df(matches), use_container_width=True, hide_index=True
                    )

        with ebs_tab:
            pmod = st.selectbox(
                "Module", [p.module for p in list_packs()], key="dict_ebs_module"
            )
            pack = get_pack(pmod)
            if pack:
                with st.container(height=260):
                    st.markdown("**Tables**")
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "table": t.table,
                                    "description": t.description,
                                    "key columns": ", ".join(t.key_columns),
                                }
                                for t in pack.tables
                            ]
                        ),
                        use_container_width=True, hide_index=True,
                    )

        st.markdown("---")
        st.markdown("**Export dictionary**")
        all_cols = [c for t in schema.tables.values() for c in t.columns]
        df_export = _columns_df(all_cols)
        e1, e2, e3 = st.columns(3)
        with e1:
            st.download_button(
                "CSV", data=dataframe_to_csv_bytes(df_export),
                file_name="data_dictionary.csv", mime="text/csv",
                use_container_width=True,
            )
        with e2:
            st.download_button(
                "Excel",
                data=dataframe_to_excel_bytes(df_export, sheet_name="Dictionary"),
                file_name="data_dictionary.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with e3:
            st.download_button(
                "Markdown", data=schema.to_compact_markdown().encode("utf-8"),
                file_name="data_dictionary.md", mime="text/markdown",
                use_container_width=True,
            )

    with right:
        table = st.selectbox(
            "Select a table", options=schema.list_tables(),
            key="dict_table", label_visibility="collapsed",
        )
        if table:
            st.markdown(f"**{table}**")
            with st.container(height=200):
                st.dataframe(
                    _columns_df(table_detail(schema, table)),
                    use_container_width=True, hide_index=True,
                )
            r1, r2 = st.columns(2)
            with r1:
                st.markdown("**References out** (this table's FKs)")
                out = references_out(schema, table)
                if out:
                    st.dataframe(
                        pd.DataFrame(out, columns=["column", "to_table", "to_column"]),
                        use_container_width=True, hide_index=True,
                    )
                else:
                    st.caption("None.")
            with r2:
                st.markdown("**Where used** (tables referencing this one)")
                inbound = referenced_by(schema, table)
                if inbound:
                    st.dataframe(
                        pd.DataFrame(inbound, columns=["from_table", "from_column", "to_column"]),
                        use_container_width=True, hide_index=True,
                    )
                else:
                    st.caption("None.")


# --------------------------------------------------------------------------- #
# Query Builder — 2-panel: NL controls left · SQL editor + results right
# --------------------------------------------------------------------------- #
def draw_query_builder(conn_cfg: Optional[OracleConnectionConfig], schema: Optional[Schema]):
    client = OracleClient(conn_cfg) if conn_cfg else None
    left, right = st.columns([1, 2])

    with left:
        mode = st.radio(
            "Mode", ["Natural Language", "Raw SQL"], horizontal=True, key="qb_mode"
        )

        if mode == "Natural Language":
            prompt = st.text_area(
                "Question",
                placeholder="Show me total AP invoices by vendor for last quarter",
                height=90,
                label_visibility="collapsed",
                key="qb_prompt",
            )
            ebs_mods = st.multiselect(
                "EBS modules",
                ["GL", "AP", "AR", "PO", "OM"],
                key="nl_ebs_modules",
                placeholder="EBS module context (optional)",
                label_visibility="collapsed",
            )
            if st.button("Generate SQL", use_container_width=True, key="qb_generate"):
                if not schema:
                    st.error("Load a schema in Schema Sources first.")
                else:
                    try:
                        result = generate_sql_from_nl(
                            prompt, schema,
                            llm=st.session_state.llm_config,
                            ebs_modules=ebs_mods or None,
                        )
                        if not result.answerable:
                            # Off-topic / unanswerable from the schema — no SQL proposed.
                            st.session_state.generated_sql = ""
                            st.session_state.nl_explanation = None
                            st.session_state.nl_confidence = None
                            st.info(result.message or "I can only answer questions about the available data.")
                        else:
                            st.session_state.generated_sql = result.sql
                            st.session_state.nl_explanation = result.explanation
                            st.session_state.nl_confidence = (
                                {"level": result.confidence.level, "reasons": result.confidence.reasons}
                                if result.confidence else None
                            )
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Generation failed: {e}")

            conf = st.session_state.nl_confidence
            if conf:
                badge = {"High": "🟢", "Medium": "🟡", "Low": "🔴"}.get(conf["level"], "⚪")
                reasons = f" · {'; '.join(conf['reasons'])}" if conf.get("reasons") else ""
                st.caption(f"{badge} {conf['level']} confidence{reasons}")
        else:
            st.caption("Write your SELECT query in the editor →")
            if not conn_cfg:
                st.caption("⚠️ No connection configured.")

    with right:
        if not conn_cfg:
            st.warning("Configure a connection in the sidebar to run queries.")

        if mode == "Natural Language":
            sql_val = st.text_area(
                "Generated SQL (editable)",
                value=st.session_state.generated_sql,
                height=160,
                key="qb_nl_sql",
            )
            st.session_state.generated_sql = sql_val
            if st.button(
                "▶ Run SQL", type="primary", use_container_width=True, key="qb_nl_run"
            ):
                if not client:
                    st.error("No connection — configure one in the sidebar.")
                elif sql_val.strip():
                    _execute_query(client, sql_val)
                else:
                    st.info("Generate SQL first, then click Run.")
        else:
            raw_sql = st.text_area(
                "SQL (SELECT only)",
                placeholder="SELECT * FROM some_table WHERE ROWNUM <= 100",
                height=160,
                key="qb_raw_sql",
            )
            if st.button(
                "▶ Run SQL", type="primary", use_container_width=True, key="qb_raw_run"
            ):
                if not client:
                    st.error("No connection — configure one in the sidebar.")
                elif raw_sql.strip():
                    _execute_query(client, raw_sql)
                    st.session_state.generated_sql = raw_sql

        df = st.session_state.get("last_results")
        expl = st.session_state.nl_explanation

        if df is not None:
            tab_names = ["Results"]
            if expl and mode == "Natural Language":
                tab_names.append("Explanation")
            result_tabs = st.tabs(tab_names)
            with result_tabs[0]:
                _render_results(df, email_key="qb_email")
            if len(result_tabs) > 1:
                with result_tabs[1]:
                    st.write(expl)


# --------------------------------------------------------------------------- #
# Helpers for Reports
# --------------------------------------------------------------------------- #
def _profile_options(store: JsonFileProfileStore) -> Dict[str, Optional[str]]:
    """Map display label → profile id, with a leading '— none —' → None."""
    labels: Dict[str, Optional[str]] = {"— none —": None}
    for p in store.list():
        labels[f"{p.name}  ·  {p.environment}"] = p.id
    return labels


# --------------------------------------------------------------------------- #
# Reports — 2-panel: saved reports left · run/save tabs right
# --------------------------------------------------------------------------- #
def draw_reports(conn_cfg: Optional[OracleConnectionConfig]):
    rstore = get_report_store()
    pstore = get_store()
    reports = rstore.list()

    left, right = st.columns([1, 2])

    with left:
        st.markdown("##### Saved reports")
        if not reports:
            st.info("No reports yet. Build a query and save it using the 'Save New' tab →")
        else:
            report_names = [r.name for r in reports]
            selected_name = st.selectbox(
                "Report", report_names, key="rep_select", label_visibility="collapsed"
            )
            selected = next(r for r in reports if r.name == selected_name)
            st.session_state.selected_report_id = selected.id
            if selected.description:
                st.caption(selected.description)

    with right:
        run_tab, save_tab = st.tabs(["Run", "Save new report"])

        with run_tab:
            if not reports:
                st.info("No saved reports. Use 'Save new report' to create one.")
            else:
                report = next(
                    (r for r in reports if r.id == st.session_state.selected_report_id),
                    reports[0],
                )
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
                rc1, rc2 = st.columns([2, 1])
                with rc1:
                    target_choice = st.selectbox(
                        "Run against",
                        list(prof_labels.keys()),
                        index=list(prof_labels.keys()).index(bound_label),
                        key=f"rep_target_{report.id}",
                    )
                with rc2:
                    run_clicked = st.button(
                        "▶ Run", type="primary",
                        use_container_width=True, key=f"rep_run_{report.id}",
                    )

                if run_clicked:
                    provided = {k: v for k, v in raw_values.items() if v != ""}
                    try:
                        binds = coerce_report_binds(report.parameters, provided)
                    except ValueError as e:
                        st.error(str(e))
                    else:
                        target_profile_id = prof_labels[target_choice]
                        client: Optional[OracleClient] = None
                        if target_profile_id:
                            try:
                                resolved = pstore.resolve(target_profile_id)
                                client = OracleClient(_resolved_to_cfg(resolved)) if resolved else None
                            except SecretConfigError as e:
                                st.error(
                                    f"{e} (ref: {log_error_for_ui(e, context='ui.secret_config')})"
                                )
                        elif conn_cfg:
                            client = OracleClient(conn_cfg)
                        if client is None:
                            st.warning(
                                "No connection — bind a profile, pick one above, or set "
                                "the sidebar connection."
                            )
                        else:
                            _execute_query(client, report.sql, binds=binds)

                df = st.session_state.get("last_results")
                if df is not None:
                    _render_results(df, email_key="rep_email")

                st.markdown("---")
                if st.button(
                    f"Delete '{report.name}'",
                    key=f"rep_del_{report.id}",
                ):
                    rstore.delete(report.id)
                    st.session_state.selected_report_id = None
                    st.success(f"Deleted '{report.name}'.")
                    st.rerun()

        with save_tab:
            current_sql = st.session_state.generated_sql or ""
            if not current_sql.strip():
                st.info(
                    "Generate or type SQL in Query Builder first, or load a template. "
                    "It will appear here for saving."
                )
            else:
                st.code(current_sql, language="sql")
                save_name = st.text_input("Report name", key="rep_save_name")
                description = st.text_input("Description (optional)", key="rep_save_desc")

                params: List[ReportParam] = []
                for pname in _detect_params(current_sql):
                    pc1, pc2, pc3 = st.columns([1, 1, 2])
                    with pc1:
                        ptype = st.selectbox(
                            f":{pname} type", ["string", "number", "date"],
                            key=f"savep_type_{pname}",
                        )
                    with pc2:
                        preq = st.checkbox("required", value=True, key=f"savep_req_{pname}")
                    with pc3:
                        pdef = st.text_input("default", key=f"savep_def_{pname}")
                    params.append(
                        ReportParam(name=pname, type=ptype, required=preq, default=(pdef or None))
                    )

                bind_label = st.selectbox(
                    "Bind to profile (optional)",
                    list(_profile_options(pstore).keys()),
                    key="rep_save_bind",
                )
                if st.button("Save report", type="primary", key="rep_save_btn", use_container_width=True):
                    if not save_name.strip():
                        st.error("Provide a report name.")
                    else:
                        try:
                            rstore.create(
                                ReportCreate(
                                    name=save_name,
                                    description=description,
                                    sql=current_sql,
                                    parameters=params,
                                    default_profile_id=_profile_options(pstore)[bind_label],
                                )
                            )
                            st.success(f"Saved report '{save_name}'.")
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))


# --------------------------------------------------------------------------- #
# Templates — 2-panel: module/list left · SQL detail right
# --------------------------------------------------------------------------- #
def draw_templates():
    templates = list_templates()
    left, right = st.columns([1, 2])

    with left:
        modules = sorted({t.module for t in templates})
        module = st.selectbox("Module", modules, key="tpl_module")
        in_mod = [t for t in templates if t.module == module]
        tpl_name = st.radio(
            "Template",
            [t.name for t in in_mod],
            key="tpl_select_radio",
            label_visibility="collapsed",
        )
        tpl = next(t for t in in_mod if t.name == tpl_name)

    with right:
        st.markdown(f"**{tpl.name}** · {tpl.module}")
        st.caption(tpl.description)
        if tpl.parameters:
            st.markdown(
                "**Parameters:** " + ", ".join(f"`:{p.name}` ({p.type})" for p in tpl.parameters)
            )
        with st.container(height=260):
            st.code(tpl.sql, language="sql")

        c1, c2 = st.columns(2)
        with c1:
            if st.button(
                "Load into Query Builder", key="tpl_load",
                use_container_width=True, type="primary",
            ):
                st.session_state.generated_sql = tpl.sql
                st.session_state.nl_explanation = None
                st.session_state.nl_confidence = None
                st.success("Loaded — switch to Query Builder to run.")
        with c2:
            save_name = st.text_input(
                "Save as report — name", value=tpl.name,
                key="tpl_save_name", label_visibility="collapsed",
            )
            if st.button("Save as report", key="tpl_save", use_container_width=True):
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
# Settings — 2-panel: LLM left · active config + email status right
# --------------------------------------------------------------------------- #
def draw_settings():
    left, right = st.columns([1, 1])

    with left:
        st.markdown("##### LLM provider")
        st.caption(
            "Choose how natural-language questions are turned into SQL. Your API key "
            "is held only in this session and is never written to disk."
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
            DEFAULT_GROQ_MODEL if provider == "Groq"
            else DEFAULT_OPENAI_MODEL if provider == "OpenAI"
            else ""
        )
        model = st.text_input(
            "Model (optional)",
            value=(current.model if current and current.model else ""),
            placeholder=model_placeholder,
        )
        api_key = st.text_input(
            "API key (optional — leave blank to use server env key)",
            type="password",
        )
        if st.button("Save LLM settings", use_container_width=True, type="primary"):
            if provider.startswith("Server default"):
                st.session_state.llm_config = None
                st.success("Using the server's default LLM configuration.")
            else:
                prov = "groq" if provider == "Groq" else "openai"
                st.session_state.llm_config = LLMConfig(
                    provider=prov, model=model or None, api_key=api_key or None
                )
                st.success(f"Saved {provider} settings for this session.")

    with right:
        st.markdown("##### Active configuration")
        cfg = st.session_state.llm_config
        if cfg is None:
            st.info("Active: server default (environment configuration).")
        else:
            key_state = "your session key" if cfg.api_key else "server env key"
            st.info(
                f"Active: {cfg.provider} · model = {cfg.model or 'provider default'} "
                f"· key = {key_state}"
            )

        st.markdown("---")
        st.markdown("##### Email")
        if email_enabled():
            st.success("Email enabled — SMTP configured via environment.")
        else:
            st.info(
                "Email disabled. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD environment "
                "variables to enable."
            )

        st.markdown("---")
        st.markdown("##### Safety")
        st.info(
            "SELECT-only mode is always active. All queries pass through the safety "
            "chokepoint before execution. This cannot be disabled."
        )


# --------------------------------------------------------------------------- #
# Layout — left-nav sidebar over a single app with shared session state
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
st.sidebar.caption("**Active connection**")
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
