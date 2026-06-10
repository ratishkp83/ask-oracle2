# Phase 5 — Independent Adversarial Review & QA (R2, post-remediation)

> **Reviewer:** Independent fresh-context agent (not the author) · **Date:** 2026-06-10
> **Phase:** Phase 5 — Data Dictionary Browser & Schema Tools
> **r1 verdict:** FAIL (1 blocking, F-1/S2) — [phase-5-review-r1.md](phase-5-review-r1.md)
> **Remediation change set:** `865719a..HEAD` — fix commit `ee14e70` ("remediate F-1..F-5").
> **Gate:** [External Review & QA Gate](../process/external-review-gate.md) · **Prompt:** [adversarial-reviewer-prompt.md](../process/adversarial-reviewer-prompt.md)
> **Environment:** `.venv` Python 3.13.2 · `pytest` **159 passed** · mocked DB throughout (no live Oracle/LLM).

---

## 1. Verdict

**PASS-WITH-FIXES.**

The single r1 blocker (**F-1, S2** — metadata-only persistence not enforced) is **fixed and independently re-verified**: a poison `POST /schemas` body now persists **only** `{tables, relationships}`; every injected secret, row-data, connection string, and even extra column-level/nested keys are dropped. No open S1/S2 remain, so **Phase 5 clears the gate.**

The remaining open items are all **non-blocking and tracked**: F-2's *400-path* verbatim-error leak is explicitly deferred to [ITM-015](../issue-log.md) (Phase-7, fix uniformly across all endpoints) — **deferral confirmed acceptable** (rationale in §3); F-4's pin reconciliation is done, with one residual caveat I could not close myself (a from-scratch venv install). One new **S4** cosmetic note (N-1) was found in the rewritten `schema_from_dict`; it breaks no invariant.

The chokepoint / bind-not-interpolate / `ALL_*`-only / target-parity safety story from r1 still holds — the remediation did not weaken it.

---

## 2. Remediation re-verification (per r1 finding)

| r1 ID | r1 Sev | Fix (commit `ee14e70`) | Re-test I ran | Result |
|-------|--------|------------------------|---------------|--------|
| **F-1** | **S2 (blocking)** | `create_schema` normalizes `definition = schema_to_dict(schema_from_dict(body.definition))` ([`api.py:495-501`](../../src/api.py)); `schema_from_dict` rewritten whitelist-only ([`schema.py:283-337`](../../src/schema.py)) — reads only the 7 known column fields + `{from,to}_*`/`relationship_type`, ignores everything else. | `POST /schemas` with `db_password`, `rows` (SSNs), `connection_string`, a nested `evil` dict, **and** an extra `db_password` key *inside* a column dict; then `GET /schemas/{id}`. | **PASS** — stored keys = `['relationships','tables']`; column fields = exactly the 7 metadata fields; **none** of `hunter2-SECRET / 123-45-6789 / connection_string / db_password / evil / inline-secret` survive. Author regression `test_create_schema_strips_non_metadata` + `test_schema_from_dict_drops_unknown_keys` are real (assert the tokens are absent). |
| **F-2** | S3 | 200-path degradation warnings made generic ("Primary keys unavailable for this account."); raw `exc` now `logger.info(...)` server-side only ([`introspection.py:164-184`](../../src/core/introspection.py)). 400-path `str(exc)` **deferred → ITM-015**. | `LeakyClient` raising `ORA-12514 … host=db-prod-internal:1521` on the PK/FK query (200 path); separate `boom` client for the 400 path. | **PASS (200-path)** — warnings contain no `ORA`/host/port tokens. **400-path still verbatim** (`ORA-00942: table SYS.SECRET_INTERNAL @ host=prod-db-01`) — as documented, deferred. Regression `test_introspect_schema_degrades_gracefully` now asserts `"ORA" not in w`. |
| **F-3** | S3 | `schema_from_dict` never raises (type-guards + `.get()` defaults); UI **Load** wrapped in `try/except` ([`app.py:459-468`](../../src/app.py)). | `schema_from_dict(None / [1,2] / {"tables":"x"} / {"tables":{"X":["nope"]}} / {"tables":{"X":[{"foo":1}]}})`. | **PASS** — all five malformed inputs return an empty/partial schema, **zero** exceptions. Defense-in-depth (tolerant function *and* guarded caller). Regression `test_schema_from_dict_tolerates_malformed` present. |
| **F-4** | S3 | `requirements.txt` now pins `sqlglot==30.10.0`, `pydantic==2.13.4`, `oracledb==4.0.1`, `cryptography==48.0.1`, with an inline comment on *why* sqlglot is pinned exactly (parse-behaviour → fail-closed). | `importlib.metadata.version(...)` vs pins; `pip check`; full suite. | **PASS (with caveat)** — installed versions **exactly equal** the pins; `pip check` → "No broken requirements found"; suite **159 green on the pinned set** (green == shipped). Caveat: I verified *installed == pinned*, not a from-scratch `pip install` into an empty venv (§5). |
| **F-5** | S4 | Dropped `min_length=1` on `IntrospectRequest.owner`; blank/whitespace normalized to a uniform `400` by the orchestrator ([`api.py:153-155`](../../src/api.py), [`introspection.py:148-150`](../../src/core/introspection.py)). | `owner` = `""` / `"   "` / `"\t"` via `POST /schemas/introspect`. | **PASS** — all three return **400** (was 422 for `""`). Missing-field still correctly 422 (`owner` required). Regression `test_introspect_empty_owner_is_400` present. |

---

## 3. F-2 400-path deferral — confirmed acceptable

The r2 scope asks whether deferring the introspect **400** verbatim-error path to [ITM-015](../issue-log.md) is acceptable rather than re-raising it as blocking. **It is**, for three reasons:

1. **Not new, not Phase-5-specific.** The same `raise HTTPException(400, str(exc))` pattern predates Phase 5 and is shared by `/execute` ([`api.py:355,360`](../../src/api.py)), `/test-connection` ([`api.py:251`](../../src/api.py)), and `/profiles/{id}/test` ([`api.py:230`](../../src/api.py)). The introspect 400 path merely follows house style; it is not a Phase-5 regression.
2. **The genuinely new surface is fixed.** The 200-success `warnings[]` — the one new place Phase 5 added where internals could leak on a *non-error* path — is remediated (F-2 above).
3. **Severity S3, not a secret.** Oracle error text carries object/host/service names, not credentials (no password in `ORA-00942`/`ORA-12514`), and they are the caller's *own* connection's details. A piecemeal scrub on introspect alone would create inconsistency and a false sense of coverage; a uniform Phase-7 fix across every endpoint is the correct architecture.

**Recommendation (non-blocking):** ITM-015 should scrub/generic-ize error `detail` for **all** DB-touching endpoints together, logging raw `exc` server-side — and add one regression per endpoint. Until then, operators should know API error details echo DB internals (host/object names).

---

## 4. New finding (introduced by the remediation)

| ID | Sev | Category | Location | Description | Repro | Recommended fix |
|----|-----|----------|----------|-------------|-------|-----------------|
| **N-1** | **S4** | Cosmetic / internal consistency | [`src/schema.py:308`](../../src/schema.py) | The rewritten `schema_from_dict` keeps a column's own `table_name` (`str(c.get("table_name") or tname)`) even when it differs from the containing table key, so a column can live under `tables["X"]` while carrying `table_name="Y"`. Pure metadata (no secret/row-data — invariant 5 still holds), but an internal inconsistency that survives the round-trip into `schemas.json`. | `schema_to_dict(schema_from_dict({"tables":{"X":[{"column_name":"C","table_name":"Y"}]}}))` → column under `X` has `table_name:"Y"`. | Normalize `table_name` to the containing table key on reconstruction (ignore the per-column value), so the key and the field can't disagree. Non-blocking. |

No other regressions found: `schema_from_dict`'s signature change (`Dict[str,object]`→`object`) is compatible with all three callers; the round-trip test and full suite are green. (Trivia: `schema.py` ends without a trailing newline — ignorable.)

---

## 5. QA results (executed this round)

| Check | Method | Result |
|---|---|---|
| Full suite | `pytest -q` on `.venv` | **159 passed**, 1 cosmetic deprecation warning (`httpx`/starlette TestClient). |
| Pins == installed | `importlib.metadata` vs `requirements.txt` | **Match** — sqlglot 30.10.0 / pydantic 2.13.4 / oracledb 4.0.1 / cryptography 48.0.1. |
| Dependency consistency | `pip check` | "No broken requirements found." |
| F-1 metadata-only | poison-blob `POST /schemas` → `GET` | **PASS** — only `{tables, relationships}`; all injected tokens dropped. |
| F-2 200-path | `LeakyClient` ORA error → `warnings[]` | **PASS** — generic; no `ORA`/host/port. |
| F-2 400-path | `boom` client → introspect `detail` | **Still verbatim** (deferred ITM-015; acceptable §3). |
| F-3 tolerance | 5 malformed `schema_from_dict` inputs | **PASS** — no raise. |
| F-5 owner | `""` / `"   "` / `"\t"` | **PASS** — uniform 400. |
| **Inv-1/7 regression — chokepoint** | `grep` `oracledb.connect`/`cur.execute`/`.cursor()` across `src/` | **PASS** — still exactly one each in [`db.py:113,140,141`](../../src/db.py); remediation added no DB path. |
| **Inv-2 regression — bind inertness** | builders × hostile owners (`X' OR '1'='1`, stacked `DROP`, 4000-char) | **PASS** — 9/9: safe SELECT, value bound, SQL text inert. |
| **Inv-6 regression — target parity** | (covered r1; endpoints untouched by `ee14e70`) | Unchanged — `IntrospectRequest` validator + `_resolve_target` not modified except the `owner` field. |

---

## 6. Could-not-verify

- **From-scratch dependency install** — I confirmed the running `.venv` versions *exactly equal* the new pins and that `pip check` is clean (so the 159-green run is genuinely on the pinned set), but I did **not** create a brand-new empty venv and run `pip install -r requirements.txt` end-to-end. If CI does this, F-4 is fully closed; recommend a clean-room install in CI as the standing proof.
- **Live Oracle** — unchanged from r1: real `ALL_*` shapes / privilege / `truncated`-under-volume still validated only against the safety layer + synthetic rows (RISK-04). Fail-closed and bind-not-interpolate do not depend on a live DB and were re-verified.
- **Browser UI** — F-3's UI-Load `try/except` guard verified by source read; not exercised in a running browser (headless only).
- **F-2 400-path in production** — confirmed the leak persists by design (deferred); the eventual ITM-015 fix is not yet present to verify.

---

## 7. Disposition

| r1 finding | r2 status |
|---|---|
| F-1 (S2, blocking) | **Closed** — fixed & verified. |
| F-2 (S3) | **Partially closed** — 200-path fixed; 400-path **deferred → ITM-015** (accepted). |
| F-3 (S3) | **Closed** — fixed & verified. |
| F-4 (S3) | **Closed** (caveat: clean-room install to be proven in CI). |
| F-5 (S4) | **Closed** — fixed & verified. |
| N-1 (S4, new) | Open — cosmetic, non-blocking; log to issue-log. |

**No open blocking items. Phase 5 → gate cleared (PASS-WITH-FIXES).** Carry F-2(400-path)/ITM-015 and N-1 forward as tracked non-blockers.
