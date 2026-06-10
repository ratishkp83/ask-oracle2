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
- ITM-008: (deferred from F3) optional NL-question PII scrubbing before external send. Current mitigation: question text is sent by design; tenants set `LLM_POLICY=external_disabled`. Rationale: the question is the user's own intent; scrubbing risks degrading legitimate queries. Revisit with the redaction/policy work.
- ITM-009: pre-existing CORS `allow_origins=["*"]` + `allow_credentials=True` + `0.0.0.0` bind (`src/api.py`) — harden (specific origins, auth) before any multi-tenant deployment. Flagged by Phase-3 reviewer §5; out of Phase-3 scope.

## Phase 3 — independent review (r1) findings & remediation

Source: [reviews/phase-3-review-r1.md](reviews/phase-3-review-r1.md) (verdict: FAIL — 2 blocking). All remediated in this iteration; 75 tests green.

| ID | Sev | Finding | Disposition | Status |
|----|-----|---------|-------------|--------|
| F1 | S2 | Confidence `High` on a nonsensical join (design §6 join signal not implemented) | **Fixed** — join predicates validated against `schema.relationships`; capped at Medium when joins present but no relationship metadata | Fixed (regression: `test_llm_confidence.py`) |
| F2 | S2 | `RetryError[...]` repr leaked as the API error on provider-call failure | **Fixed** — `reraise=True` + wrap in clean `LLMError` | Fixed (unit + HTTP-layer tests) |
| F3 | S3 | Tripwire scans schema context only; NL question sent verbatim; package wording oversold | **Fixed (wording)** + **Deferred** scrubbing → ITM-008 | Fixed/Deferred |
| F4 | S3 | Unvalidated per-request `base_url` (SSRF surface) | **Fixed** — `validate_base_url` (https + block private/loopback/link-local/metadata) | Fixed ([RISK-11](risk-register.md); DNS-rebinding residual) |
| F5 | S3 | Column resolution global, not per-table | **Fixed** — per-table (qualified) / referenced-tables (unqualified) resolution | Fixed |
| F6 | S4 | `api_key` printed by `LLMConfig`/`LLMSettings` repr | **Fixed** — `repr=False` on both | Fixed |

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Engineering | Initial log; Phase-2 defects recorded as Fixed. |
| 1.1 | 2026-06-10 | Engineering | Phase-3 r1 findings F1–F6 logged + remediated; ITM-008/009 added. |
