from __future__ import annotations

import os
import sys
from typing import List, Optional, Tuple

# Make the repo root importable so `streamlit run src/app.py` works from any CWD.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src.db import OracleClient, OracleConnectionConfig
from src.core.profiles import JsonFileProfileStore, ProfileCreate, ProfilePublic
from src.core.crypto import SecretConfigError
from src.schema import (
    Schema,
    attach_relationships,
    parse_relationships_dataframe,
    parse_schema_dataframe,
)
from src.nl2sql import (
    DEFAULT_GROQ_MODEL,
    DEFAULT_OPENAI_MODEL,
    LLMConfig,
    generate_sql_from_nl,
)
from src.utils import read_tabular_file, dataframe_to_csv_bytes, dataframe_to_excel_bytes
from src.storage import (
    load_connection_config,
    save_connection_config,
    list_reports,
    save_report,
    get_report,
    delete_report,
)

load_dotenv()

st.set_page_config(page_title="Ask Oracle Reports", layout="wide")

# --- session state -------------------------------------------------------- #
if "schema" not in st.session_state:
    st.session_state.schema = None  # type: Optional[Schema]
if "conn_config" not in st.session_state:
    st.session_state.conn_config = load_connection_config() or {}
if "last_results" not in st.session_state:
    st.session_state.last_results = None  # type: Optional[pd.DataFrame]
if "generated_sql" not in st.session_state:
    st.session_state.generated_sql = ""
if "llm_config" not in st.session_state:
    st.session_state.llm_config = None  # type: Optional[LLMConfig]


def get_store() -> JsonFileProfileStore:
    return JsonFileProfileStore()


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
    except Exception as e:  # noqa: BLE001 - surface a friendly message
        return False, f"Connection failed: {e}"


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

    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("Save", use_container_width=True):
            st.session_state.conn_config = {
                "host": host,
                "port": int(port),
                "service_name": service_name or None,
                "sid": sid or None,
                "username": username,
                "password": password,
            }
            save_connection_config(st.session_state.conn_config)
            st.sidebar.success("Saved connection configuration.")
    with col2:
        test_clicked = st.button("Test", use_container_width=True)

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
        st.sidebar.error(str(e))
        return None
    if resolved is None:
        st.sidebar.error("Selected profile could not be resolved.")
        return None

    cfg_obj = _resolved_to_cfg(resolved)
    if st.sidebar.button("Test connection", use_container_width=True):
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
            st.error(str(e))
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
        use_container_width=True,
        hide_index=True,
    )

    labels = {f"{p.name}  ·  {p.environment}": p for p in profiles}
    selected = labels[st.selectbox("Select a profile", list(labels.keys()), key="conn_select_profile")]
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Test selected", use_container_width=True, key="conn_test_selected"):
            try:
                resolved = store.resolve(selected.id)
                ok, msg = _try_connect(_resolved_to_cfg(resolved))
                (st.success if ok else st.error)(msg)
            except SecretConfigError as e:
                st.error(str(e))
    with col2:
        if st.button("Delete selected", use_container_width=True, key="conn_delete_selected"):
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
def draw_schema_upload():
    st.header("Upload Schema Metadata")
    st.write(
        "Upload a CSV/Excel file with columns: table_name, column_name, data_type, "
        "is_primary_key, is_foreign_key, references_table, references_column."
    )

    schema_file = st.file_uploader("Schema file (CSV/Excel)", type=["csv", "xlsx", "xls"])
    rel_file = st.file_uploader("Relationships (optional, CSV/Excel)", type=["csv", "xlsx", "xls"], key="rel")

    if st.button("Parse Schema"):
        if not schema_file:
            st.error("Please upload a schema file first.")
            return
        try:
            schema = parse_schema_dataframe(read_tabular_file(schema_file.read(), schema_file.name))
            if rel_file is not None:
                rels = parse_relationships_dataframe(read_tabular_file(rel_file.read(), rel_file.name))
                schema = attach_relationships(schema, rels)
            st.session_state.schema = schema
            st.success("Schema parsed and loaded.")
            with st.expander("Schema Overview", expanded=True):
                st.code(schema.to_compact_markdown())
        except Exception as e:  # noqa: BLE001
            st.error(f"Failed to parse schema: {e}")


def draw_schema_explorer(schema: Schema):
    st.header("Explore Schema")
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("Tables")
        table_selected = st.selectbox("Select table", options=schema.list_tables())
        if table_selected:
            st.write(f"Columns in `{table_selected}`:")
            st.write(pd.DataFrame({"column": schema.list_columns(table_selected)}))
    with c2:
        st.subheader("Relationships")
        if schema.relationships:
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "from_table": r.from_table,
                            "from_column": r.from_column,
                            "to_table": r.to_table,
                            "to_column": r.to_column,
                            "type": r.relationship_type or "",
                        }
                        for r in schema.relationships
                    ]
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("No relationships uploaded. You can still write explicit JOINs in SQL.")


# --------------------------------------------------------------------------- #
# Query builder
# --------------------------------------------------------------------------- #
def _run_and_display(client: OracleClient, sql: str):
    try:
        result = client.run_select(sql)
        df = pd.DataFrame(result.rows, columns=result.columns)
        st.session_state.last_results = df
        msg = f"Query OK in {result.elapsed_seconds:.2f}s, {result.row_count} rows"
        if result.truncated:
            st.warning(msg + " — result truncated by safety limits.")
        else:
            st.success(msg)
        st.dataframe(df, use_container_width=True)
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
    except Exception as e:  # noqa: BLE001 - includes SqlSafetyError
        st.error(f"Execution error: {e}")


def draw_query_builder(conn_cfg: Optional[OracleConnectionConfig], schema: Optional[Schema]):
    st.header("Build & Run Reports")
    if not conn_cfg:
        st.warning("Choose a saved profile or fill in a manual connection in the sidebar to run queries.")
    mode = st.radio("Query mode", ["Natural Language", "Raw SQL"], horizontal=True)
    client = OracleClient(conn_cfg) if conn_cfg else None

    if mode == "Natural Language":
        prompt = st.text_area("What do you want to see?", placeholder="Show me total AP invoices by vendor for last quarter")
        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Generate SQL"):
                if not schema:
                    st.error("Upload schema first.")
                else:
                    try:
                        st.session_state.generated_sql = generate_sql_from_nl(
                            prompt, schema, llm=st.session_state.llm_config
                        )
                        st.success("SQL generated. Review it below before running.")
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Failed to generate SQL: {e}")
        with col2:
            run_clicked = st.button("Run SQL")

        sql_box_val = st.text_area("Generated SQL (editable)", value=st.session_state.generated_sql, height=200)
        st.session_state.generated_sql = sql_box_val

        if run_clicked and client and sql_box_val.strip():
            _run_and_display(client, sql_box_val)

    else:  # Raw SQL
        sql = st.text_area("SQL", placeholder="SELECT * FROM some_table WHERE ROWNUM <= 100")
        if st.button("Run SQL (SELECT only)"):
            if not client:
                st.error("Configure a connection first.")
            elif sql.strip():
                _run_and_display(client, sql)


def draw_saved_reports():
    st.header("Saved Reports")
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        report_name = st.text_input("Report name", key="rep_name")
    with col2:
        save_clicked = st.button("Save current", use_container_width=True, key="rep_save")
    with col3:
        delete_clicked = st.button("Delete selected", use_container_width=True, key="rep_delete")

    existing = list_reports()
    selected = st.selectbox("Select a saved report", options=[""] + existing, key="rep_select")
    report = get_report(selected) if selected else None

    if save_clicked:
        if not report_name:
            st.error("Provide a name.")
        elif st.session_state.generated_sql:
            save_report(report_name, {"sql": st.session_state.generated_sql})
            st.success("Saved.")
        else:
            st.warning("Nothing to save. Generate or type SQL in the Query Builder first.")

    if delete_clicked and selected:
        delete_report(selected)
        st.success("Deleted.")

    if report:
        st.subheader(f"Report: {selected}")
        st.code(report.get("sql", ""))


# --------------------------------------------------------------------------- #
# Layout
# --------------------------------------------------------------------------- #
conn_cfg = draw_sidebar_connection()

_tabs = st.tabs(
    ["Connections", "Schema Upload", "Explore Schema", "Query Builder", "Saved Reports", "Settings"]
)
with _tabs[0]:
    draw_connections(get_store())
with _tabs[1]:
    draw_schema_upload()
with _tabs[2]:
    if st.session_state.schema:
        draw_schema_explorer(st.session_state.schema)
    else:
        st.info("Upload schema metadata first.")
with _tabs[3]:
    draw_query_builder(conn_cfg, st.session_state.schema)
with _tabs[4]:
    draw_saved_reports()
with _tabs[5]:
    draw_settings()
