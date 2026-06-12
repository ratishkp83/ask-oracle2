# Round C1 / B6 — GA-Readiness Verdict

> **Document:** GA-Readiness Assessment · **Version:** 1.0 · **Status:** Final · **Owner:** Delivery Lead · **Date:** 2026-06-12
> Closes Round C1 (Pre-GA Consolidation & Testing). Inputs: the full governed record (phases 1–6 + 6.5 + C1), the Round C1 review ([r1](reviews/round-C1-review-r1.md)), and the live-Oracle pass ([evidence](reviews/round-C1-live-pass.md)).

## 1. Verdict

**GA-ready** for the core product — a **read-only, AI-assisted reporting layer for Oracle
Database** — subject to the **deployment preconditions in §5**. The **EBS template pack ships as
"beta / review-before-run"** pending validation against a real E-Business Suite instance
(ITM-012). No open S1/S2 issues; every governed register is clean or has an explicit, owned
disposition.

## 2. What "GA-ready" covers
Connect (encrypted profiles) → introspect a schema (SELECT-only) → ask in natural language or
write SQL → **review** → run under safety + limits → export. The product's central promise —
**it can only read, never modify data** — is enforced by a single chokepoint and was verified
against a real database (§4).

## 3. Readiness by area

| Area | State | Basis |
|------|-------|-------|
| **SELECT-only safety** | ✅ Solid | Single chokepoint (`sql_safety.py`→`db.py`, one `connect`/`execute`); layered parse+denylist, fail-closed; **rejected `UPDATE`/`FOR UPDATE`/CTE-DML/`SELECT INTO`/stacked against live XE** |
| **AI proposes, never runs** | ✅ | `generate_sql_from_nl` returns SQL; execution is a separate user action |
| **Secrets** | ✅ | env-only; profile passwords Fernet-encrypted, never returned; single persistence path (ITM-006); no plaintext at rest |
| **NL→SQL** | ✅ | provider abstraction + policy + strict schema-name redaction + opt-in PII scrubbing (ITM-008); confidence heuristic |
| **Data dictionary / introspection** | ✅ | live SELECT-only via the chokepoint (ADR-010); validated against XE |
| **Saved reports + bind params** | ✅ | binds as values never interpolated (ADR-007); validated against XE |
| **Observability & errors** | ✅ | structured JSON logs, request/error IDs, uniform DB-error sanitization (ADR-012) |
| **Network edge** | ✅ *(opt-in)* | API-key auth + explicit CORS (ADR-013) — **must be enabled for any networked deploy** (§5) |
| **Store durability** | ✅ | atomic writes + corrupt-record quarantine (ADR-014); single-worker-per-store constraint documented |
| **CI** | ✅ | green on Python 3.11 + 3.13 (run #12 on `f374380`); 262 offline tests |
| **EBS template pack** | ⚠️ Beta | catalog proven safe + param-consistent, but **not run against real EBS** → ITM-012 |

## 4. Evidence
- **262 automated tests** green locally; **CI green on 3.11 + 3.13**.
- **Live-Oracle pass (XE 21c, read-only account):** connect / introspect / bind-parameterized
  report / CSV export / **safety-rejection of writes** — **ALL PASS**
  ([round-C1-live-pass.md](reviews/round-C1-live-pass.md)).
- **Owner browser-tested** the Streamlit UI against XE satisfactorily.
- **Independent reviews** at each phase exit (reviewer ≠ author): Phases 3/4/5/6/6.5 + Round C1 all
  reached PASS / PASS-WITH-FIXES with findings remediated.
- **All issue-log ITMs closed** (009/010/013/014/015/016/017, 006/007/008); risk register: RISK-04
  Closed, RISK-12 Closed, RISK-09 Closed, others Mitigating/Accepted with rationale.

## 5. Deployment preconditions (must hold at deploy)
1. **Least-privilege read-only Oracle account** — non-negotiable ([ADR-009](adr/ADR-009-readonly-db-account-precondition.md), [D7 §0](07-deployment-plan.md)). The safety gate is defense-in-depth *on top of* this.
2. **`APP_SECRET_KEY`** set (profile-password encryption).
3. **For any networked / non-localhost exposure:** set **`APP_API_KEY`** (enables auth) and
   **`ALLOWED_ORIGINS`** (explicit origins) — see the D7 §2 network-exposure rule. Never publish
   the API with auth unset.
4. **One worker per store directory** (file-store concurrency constraint), or move to a DB-backed
   store first (future).
5. Structured logs go to stdout; the platform owns shipping/retention.

## 6. Out of scope for this GA (deferred, with a home)
- **EBS templates vs a real EBS instance** — ITM-012 (validate before marketing EBS-specific claims).
- **Phase 7 (optional):** Oracle 23ai vector search / in-DB ML; EBS metadata packs. All its code
  preconditions are already cleared.
- **Residuals (documented, non-blocking):** DNS-rebinding on a custom `base_url` (RISK-11);
  multi-worker store concurrency (RISK-16, single-worker constraint); list/multi-value binds (ITM-011).
- **Conservative PII scrubbing** (ITM-008) is opt-in and recall<precision by design — not a
  compliance-grade DLP.

## 7. Recommendation
Ship the read-only reporting product to GA once §5 is satisfied in the target environment. Gate
EBS-template marketing claims on ITM-012. Open Phase 7 only as a deliberate, separately-chartered
feature effort.

## Revision history
| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-12 | Delivery | GA-readiness verdict closing Round C1 — GA-ready (core product) subject to §5 preconditions; EBS pack beta pending ITM-012. |
