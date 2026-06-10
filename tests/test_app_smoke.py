"""Streamlit UI smoke test (Phase-2 T-13, updated for the Phase-4 left-nav).

Uses Streamlit's headless AppTest harness to execute `src/app.py` in a real
Streamlit runtime — verifying every left-nav section renders without exceptions
and that the Connections / Settings flows work. No browser or live Oracle DB is
required: profile creation does not connect, and DML rejection happens before any
DB call.

Not covered here (needs a live Oracle sandbox / real LLM key + manual pass):
visual layout in a browser, successful DB connection/query, live NL→SQL output.
"""

import os

from streamlit.testing.v1 import AppTest

from src.storage import DEFAULT_STORAGE_DIR

APP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "app.py"
)
SECTIONS = [
    "Connections",
    "Schema Sources",
    "Data Dictionary",
    "Query Builder",
    "Reports",
    "Templates",
    "Settings",
]


def _fresh_app() -> AppTest:
    at = AppTest.from_file(APP_PATH, default_timeout=60)
    at.run()
    return at


def _nav(at: AppTest):
    return next(r for r in at.radio if r.label == "Navigate")


def test_app_boots_with_left_nav():
    at = _fresh_app()
    assert not at.exception, f"Streamlit app raised on render: {at.exception}"
    assert _nav(at).options == SECTIONS


def test_every_section_renders_without_exception():
    at = _fresh_app()
    for section in SECTIONS:
        _nav(at).set_value(section)
        at.run()
        assert not at.exception, f"Section '{section}' raised: {at.exception}"


def test_settings_llm_per_session_override():
    at = _fresh_app()
    _nav(at).set_value("Settings")
    at.run()
    assert not at.exception
    provider = next(s for s in at.selectbox if s.label == "Provider")
    provider.set_value("Groq")
    at.run()
    save = next(b for b in at.button if b.label == "Save LLM settings")
    save.click()
    at.run()
    assert not at.exception
    messages = [str(m.value) for m in at.success] + [str(m.value) for m in at.info]
    assert any("groq" in m.lower() for m in messages), messages


def test_templates_section_lists_catalog():
    at = _fresh_app()
    _nav(at).set_value("Templates")
    at.run()
    assert not at.exception
    module = next(s for s in at.selectbox if s.label == "Module")
    assert set(module.options) == {"GL", "AP", "AR", "PO", "OM"}


def test_data_dictionary_renders_with_schema():
    from src.schema import ColumnDefinition, Schema, TableDefinition

    at = AppTest.from_file(APP_PATH, default_timeout=60)
    at.session_state["schema"] = Schema(
        tables={
            "EMP": TableDefinition(
                "EMP",
                [
                    ColumnDefinition("EMP", "EMP_ID", "NUMBER", is_primary_key=True),
                    ColumnDefinition(
                        "EMP", "DEPT_ID", "NUMBER", is_foreign_key=True,
                        references_table="DEPT", references_column="DEPT_ID",
                    ),
                ],
            ),
            "DEPT": TableDefinition("DEPT", [ColumnDefinition("DEPT", "DEPT_ID", "NUMBER", is_primary_key=True)]),
        }
    )
    at.run()
    _nav(at).set_value("Data Dictionary")
    at.run()
    assert not at.exception
    assert any(ti.label == "Table or column contains" for ti in at.text_input)


def test_connections_create_profile_via_ui_encrypts_at_rest():
    profiles_path = os.path.join(DEFAULT_STORAGE_DIR, "profiles.json")
    if os.path.exists(profiles_path):
        os.remove(profiles_path)

    at = _fresh_app()  # default section is "Connections"
    assert not at.exception
    at.text_input(key="profile_name").set_value("UI Smoke DEV")
    at.text_input(key="profile_host").set_value("db.smoke.local")
    at.text_input(key="profile_service").set_value("XEPDB1")
    at.text_input(key="profile_username").set_value("reporter")
    at.text_input(key="profile_password").set_value("smoke-secret-pw")
    submit = next(b for b in at.button if b.label == "Add profile")
    submit.click()
    at.run()

    assert not at.exception
    assert any("added" in str(s.value).lower() for s in at.success), [s.value for s in at.success]

    assert os.path.exists(profiles_path)
    with open(profiles_path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    assert "smoke-secret-pw" not in raw  # encrypted at rest, not cleartext
    os.remove(profiles_path)
