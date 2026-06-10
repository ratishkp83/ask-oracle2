# D12 — Issue / Bug Log

> **Document:** Issue Log · **Version:** 1.0 · **Status:** Living · **Owner:** Engineering · **Last updated:** 2026-06-10

## Bug workflow (mandatory)

`Identify → Reproduce → Root Cause Analysis → Fix Plan → Validation → Documentation Update`

Each defect is logged with **severity** (S1 critical … S4 trivial), **impact**, and **resolution status** (Open / In Progress / Fixed / Closed / Won't Fix). A fix is not "done" until tests + docs are updated.

## Log

| ID | Title | Severity | Impact | Status | Notes / RCA |
|----|-------|----------|--------|--------|-------------|
| BUG-001 | Hardcoded API key + stubbed `/execute` in original `src/api.py` | S1 | Secret exposure; safety not enforced via API | **Fixed** | Consolidated onto wired API; key removed; chokepoint added. Validated by `test_execute_endpoint.py`. |
| BUG-002 | Prefix-only safety check rejected valid `SELECT\n…` and missed stacked/`FOR UPDATE`/PL-SQL | S2 | False rejections + safety gaps | **Fixed** | Replaced with layered sqlglot engine. Regression cases in `test_sql_safety.py`. |
| BUG-003 | `docker-compose.yml` referenced non-existent `Dockerfile` | S3 | `docker compose build` fails | **Fixed** | Repointed to `Dockerfile.api.local`. |
| OPS-004 | `.env` not in `.gitignore` (Groq key tracked) | S1 | Secret leak | **Closed** | Added `.env` to ignore; keys **rotated** by user 2026-06-10 ([RISK-01](risk-register.md)). |
| BUG-005 | App crashes (`StreamlitDuplicateElementId`) once a profile exists — duplicate `Delete selected` button across Connections + Saved Reports tabs | S2 | UI unusable whenever ≥1 saved profile | **Fixed** | Workflow: Identified+Reproduced by `test_app_smoke.py`; RCA = identical auto-generated widget IDs across tabs; Fix = unique `key=` on colliding widgets (+`sys.path` shim); Validated green (51/51). |

## Open items (non-defect, tracked)

- ITM-005: Streamlit UI not browser-verified — see [RISK-04](risk-register.md).
- ITM-006: Migrate legacy `connection.json` (plaintext) to encrypted profiles — see [RISK-09](risk-register.md).
- ITM-007: `use_container_width` is deprecated in Streamlit (removal scheduled post-2025-12-31); migrate `st.button`/`st.dataframe`/`st.download_button` calls to `width='stretch'`. Severity S4 (warning only; app functions).

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Engineering | Initial log; Phase-2 defects recorded as Fixed. |
