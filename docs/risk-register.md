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
| RISK-09 | `connection.json` (manual) stores plaintext password | Medium | Local-file credential exposure | Medium | git-ignored; migrate manual conn to encrypted profiles | Eng | Open |

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Delivery | Initial register from P2.5 issue triage. |
