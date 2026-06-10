# D10 — Risk Register

> **Document:** Risk Register · **Version:** 1.0 · **Status:** Living · **Owner:** Delivery Lead · **Last updated:** 2026-06-10

Severity: Critical / High / Medium / Low. Status: Open / Mitigating / Accepted / Closed.

| ID | Risk | Severity | Impact | Likelihood | Mitigation | Owner | Status |
|----|------|----------|--------|-----------|------------|-------|--------|
| RISK-01 | Live Groq/OpenAI keys were committed to the repo | Critical | Credential compromise, billing abuse | High (if pushed) | Files cleaned + `.env` ignored; keys **rotated** by user 2026-06-10 | User | **Closed** |
| RISK-02 | No version control on local copy | High | No history/audit; cannot govern docs | Was certain | **Resolved in P2.5** (git initialized) | Eng | Closing |
| RISK-03 | Docs fragmented (staging vs repo) | Medium | Source-of-truth ambiguity | Medium | Governed `/docs` is authoritative; staging archived | Eng | Mitigating |
| RISK-04 | Streamlit UI not browser-verified | Medium | UI regressions ship undetected | Medium | Headless AppTest smoke (`test_app_smoke.py`) now in CI; live-DB + visual/browser pass still manual | QA | Mitigating |
| RISK-05 | No CI; manual test runs | Medium | Regressions slip | Medium | GitHub Actions CI added in P2.5 | Eng | Closing |
| RISK-06 | sqlglot fail-closed rejects exotic valid SELECTs | Low | Occasional false rejection | Low | Documented tradeoff; add cases as found | Eng | **Accepted** |
| RISK-07 | "Per-user" LLM is per-session (no auth) | Low | Not true multi-tenant isolation | n/a | Revisit when identity layer added | Product | **Accepted** |
| RISK-08 | `APP_SECRET_KEY` rotation invalidates stored passwords | Low | Profiles need re-entry | Low | Documented in crypto + deployment runbook | Eng | Accepted |
| RISK-09 | `connection.json` (manual) stores plaintext password | Medium | Local-file credential exposure | Low | **Password no longer persisted** — `save_connection_config` strips it (Phase 4 r1/F5, `test_storage.py`); git-ignored; full manual→profile migration remains ([ITM-006](issue-log.md)) | Eng | **Mitigating** |
| RISK-10 | Phase 2 received author-only review (gate introduced post-closure) | Low | Possible undetected defect in Phase-2 scope | Low | Strong automated coverage (51 tests); gate applies Phase 3+ ([ADR-006](adr/ADR-006-external-review-gate.md)) | Delivery | **Accepted** |
| RISK-11 | Per-request `base_url` SSRF (F4) | Medium | Server egress to internal/metadata endpoints | Low | `validate_base_url` blocks non-https + private/loopback/link-local/metadata. **Residuals:** (a) hostname → private-IP via DNS rebinding; (b) integer/hex/octal IP encodings of loopback bypass the literal check (F7/ITM-010) — not exploitable on tested stack (`getaddrinfo` fails closed), platform-dependent | Eng | **Mitigating** |
| RISK-12 | Permissive CORS `*` + credentials + `0.0.0.0` bind (pre-existing) | Medium | Cross-origin/SSRF amplification once exposed/multi-tenant | Medium | Restrict origins + add auth before multi-tenant ([ITM-009](issue-log.md)) | Eng | Open |
| RISK-13 | Parameterized reports could re-introduce SQL injection / SELECT-only bypass | High | Read-only guarantee defeated via parameter values | Low | **Bind variables only**, never interpolated ([ADR-007](adr/ADR-007-parameterized-reports-bind-variables.md)); `validate_binds` (scalar-only); SQL-text safety check unchanged + runs first; 11 bind-safety tests (injection-as-value inert; DML-with-binds rejected) | Eng | **Mitigating** |
| RISK-14 | EBS templates assume a standard schema; may fail/mislead on customized instances | Low | Template run errors or wrong results on customized EBS | Medium | Labelled "standard EBS reference — review before running"; editable; never auto-run; live-EBS validation deferred to pre-GA pass ([RISK-04](#)) / [ITM-012](issue-log.md) | Product/Eng | **Accepted** |
| RISK-15 | A SELECT can invoke a side-effecting / autonomous-txn PL/SQL function (parse gate can't prove side-effect-freedom) — F1 | High | "No data modification" guarantee defeated *iff* a writing function + EXECUTE grant exist on the connected account | Low | **Defense in depth:** SELECT/CTE-only parse gate (ADR-001) + bind params (ADR-007) **and a required least-privilege read-only DB account** ([ADR-009](adr/ADR-009-readonly-db-account-precondition.md), [Deployment §0](07-deployment-plan.md)) — the account, not parsing, is the control. Optional parse-time package denylist available as extra defense-in-depth (owner decision; not enforced) | Eng/Ops | **Mitigating** |
| RISK-16 | File-store durability/concurrency: non-atomic writes + per-process lock (R1) | Low | Torn `reports.json`/`profiles.json`/`schemas.json` on crash; lost updates with >1 worker | Low | Single-process today; atomic temp+`os.replace` / file lock / SQLite before multi-worker (Phase 7) — [ITM-013](issue-log.md) | Eng | **Accepted** (Phase-7 gate) |
| RISK-17 | Introspecting a huge catalog (EBS) overwhelms UI / times out | Medium | Slow/blocked introspection; truncated dictionary | Low | **Scoped** (owner + name filter required/encouraged) + **capped** by `SafetyLimits` (`truncated` surfaced); on-demand, no full crawl ([ADR-010](adr/ADR-010-schema-introspection-via-chokepoint.md)) | Eng | **Mitigating** |
| RISK-18 | Persisted schema metadata sensitivity (table/column names) | Low | Local-file exposure of business metadata (no data values/creds) | Low | `schemas.json` is metadata only, git-ignored under `STORAGE_DIR` like profiles/reports | Eng | **Accepted** |

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Delivery | Initial register from P2.5 issue triage. |
| 1.1 | 2026-06-10 | Delivery | Phase 4: RISK-13 (bind-injection, mitigated by ADR-007) + RISK-14 (EBS template schema variance, accepted) added. |
| 1.2 | 2026-06-10 | Delivery | Phase 4 review r1: RISK-15 (side-effecting functions → read-only-account precondition, ADR-009) + RISK-16 (file-store durability, Phase-7) added. |
| 1.3 | 2026-06-10 | Delivery | Phase 5: RISK-17 (introspection scale, mitigated by scoping/caps) + RISK-18 (schema metadata sensitivity, accepted) added. |
