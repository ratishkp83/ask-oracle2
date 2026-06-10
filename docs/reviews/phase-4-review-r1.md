# Phase 4 — Independent Adversarial Review & QA (r1)

> **Reviewer:** Independent agent (fresh context; not the author) · **Date:** 2026-06-10
> **Phase:** Phase 4 — Reports, Templates & UX · **Change set:** `3f6c03e..HEAD` (`9766238`)
> **Inputs:** [adversarial-reviewer-prompt.md](../process/adversarial-reviewer-prompt.md) · [phase-4-charter.md](../charters/phase-4-charter.md) · [reports-templates-ux-design.md](../reports-templates-ux-design.md) · [ADR-007](../adr/ADR-007-parameterized-reports-bind-variables.md) · [ADR-008](../adr/ADR-008-reports-core-module-api-parity.md)
> **Method:** Static review of `src/db.py`, `src/api.py`, `src/core/reports.py`, `src/core/templates.py`, `src/core/sql_safety.py`, `src/core/audit.py`, `src/core/profiles.py`, `src/core/crypto.py`, `src/storage.py`, `src/app.py`; full `pytest` run (**118 passed**); a 33-case hostile SQL attack matrix against the chokepoint; bind/coercion edge probes; and API-level abuse probes via `TestClient` (DML+binds, unknown-param smuggling, password-in-response, NaN binds). All probes ran against a **mocked DB** — no live Oracle/LLM calls.

---

## 1. Verdict

**`PASS-WITH-FIXES`**

No blocking findings (no S1, **no S2**). Every headline invariant held under attack:

- **SELECT/CTE-only, fail-closed** — all 18 genuine write/PL-SQL/stacked/`FOR UPDATE` attacks were rejected (DML, DDL, MERGE, `INSERT … RETURNING`, anonymous `BEGIN/DECLARE` blocks, CTAS, stacked `;`, comment-hidden DML, `FOR UPDATE [OF]`, `UNION … FOR UPDATE`, PG-style `WITH … DELETE RETURNING`). Binds do **not** weaken this: `DELETE … WHERE id = :id` with `binds={id:1}` still 400s.
- **Single chokepoint** — there is exactly **one** `cur.execute` in the codebase (`db.py:137`) and one `oracledb.connect` (`db.py:109`), both reachable only through `OracleClient.run_select`, which calls `assert_safe_select` first. UI and both API run paths (`/execute`, `/reports/{id}/run`) converge there. **Zero** string-interpolation of SQL or bind values anywhere — ADR-007 holds.
- **Secrets** — diff scan clean; `ProfilePublic` (and the OpenAPI schema) carry no password; a created password never appears in any create/get response; passwords are Fernet-encrypted at rest and only `resolve()` (internal) decrypts.
- **Limits** — `max_rows` narrows only (`max(1, min(req, global))`); `truncated` is computed by a real look-ahead fetch.
- **Audit** — records a 16-char SHA-256 prefix + metadata only; no raw SQL, no credentials, on allowed or rejected paths.

The open items are S3/S4: two SELECT-shaped constructs that pass the gate without being writes on Oracle (defense-in-depth, not bypasses), lax `number` coercion, a doc/code drift, and pre-existing file-store/secret-hygiene robustness gaps. None gate closure. **F1 is flagged for an owner severity decision** (see §3).

---

## 2. Findings table

| ID | Severity | Category | Location (file:line) | Description | Reproduction / exploit (exact input) | Recommended fix |
|----|----------|----------|----------------------|-------------|---------------------------------------|-----------------|
| **F1** | **S3** *(owner: consider S2 — see §3)* | Safety — side-effecting functions | `src/core/sql_safety.py:122-136` (no function denylist) | A `SELECT` that **calls a PL/SQL function** passes the gate. Static parsing proves "is a SELECT", not "has no side effects". `DBMS_LOCK.SLEEP` is accepted (DoS, but bounded by `conn.call_timeout`); more importantly a SELECT can invoke a function that performs an **autonomous-transaction DML**, so "SELECT-only" ≠ "no writes" *if such a function and `EXECUTE` privilege exist on the connected account*. Inherent limitation of any parse-based allowlist; the real control is a least-privilege read-only DB account, which the product **relies on but does not enforce or document as a hard precondition**. | `assert_safe_select("SELECT DBMS_LOCK.SLEEP(1) FROM dual").allowed` → `True` (verified). Write path requires a pre-existing autonomous-txn function + execute grant. | Make the **read-only / least-privilege Oracle account a documented, non-negotiable deployment precondition** (BRD/architecture + run docs). Optionally add a package/function denylist (`DBMS_LOCK`, `DBMS_LOB`, `UTL_*`, `DBMS_SQL`, …) and reject `exp.Anonymous` calls to unknown functions. Add a regression test. |
| **F2** | S3 | Safety — fail-closed principle | `src/core/sql_safety.py:114-136` | `SELECT … INTO …` passes the gate (`assert_safe_select("SELECT x INTO y FROM emp").allowed` → `True`). On Oracle this is PL/SQL-only and errors at the DB (not a write), but `SELECT … INTO <newtable>` **creates a table in T-SQL/Postgres dialects** — accepting an `into` clause is not a pure read-only projection and breaks the fail-closed stance. Trivially blockable. | `assert_safe_select("SELECT x INTO y FROM emp").allowed` → `True` (verified). | Reject a root `exp.Select` that carries an `into` arg with a clear reason; add a test alongside the `FOR UPDATE` case. |
| **F3** | S3 | Input validation — bind coercion | `src/core/reports.py:115-127` (`_coerce_value` number branch); `src/db.py:30,49` (`float` ∈ allowed bind types) | A `type="number"` parameter accepts **non-finite** values: `"nan"`, `"inf"`, `"-inf"`, `"1e400"` are coerced to Python `float('nan')/float('inf')` and pass `validate_binds` (they are `float`). Not a safety bypass (still a bind *value*), but at a real Oracle NUMBER bind this raises a driver error at execution, surfacing as a generic 400 "DB error" instead of a clean "must be a number" 400. | `POST /reports/{id}/run {binds:{org_id:"nan"}}` → **200** with bound value `{'org_id': nan}` (verified via mocked DB). | In `_coerce_value` (and/or `validate_binds`) reject non-finite floats via `math.isfinite`; raise the existing "must be a number" `ValueError`. Add `nan`/`inf` to `test_reports.py`. |
| **F4** | S4 | Contract / code drift | `src/api.py:103-107` (`SQLExecuteRequest._require_target`); `docs/05-api-contracts.md` (`/execute` "→ 422 neither/both target supplied") | The contract says `/execute` rejects **both** `profile_id` and `connection` with `422`. The validator only rejects **neither**; supplying *both* is accepted and silently **prefers the profile** (`_resolve_target` checks `profile_id` first). `RunReportRequest` (api.py:110-119) has the same unresolved precedence. | `POST /execute {sql, profile_id:"x", connection:{…}}` → not 422; profile path taken. | Either enforce mutual exclusivity (reject when both present) **or** amend the doc to state "profile wins when both supplied". Pick one and add a test. |
| **F5** | S3 *(pre-existing; not introduced by Phase 4)* | Secret at rest — legacy path | `src/app.py:114-123`; `src/storage.py:24-27` (`save_connection_config`) | The Streamlit sidebar **manual-entry "Save"** writes the password **in cleartext** to `storage/connection.json`. Profiles are Fernet-encrypted, but this legacy single-connection path is not — a partial contradiction of the "passwords encrypted at rest" invariant. Mitigated: `storage/` is git-ignored (never committed) and it is a local-only file. | Save a manual connection in the UI → inspect `storage/connection.json` → plaintext `"password"`. | Encrypt via `crypto.encrypt_secret` on save / decrypt on load, **or** drop the manual-save path in favour of profiles, **or** document it as dev-only and warn in the UI. Track in issue log. |
| **F6** | S3 | Error handling — info disclosure | `src/api.py:311-315` (`_run_sql` generic branch), `203-206` (`/test-connection`), `184-185` (`/profiles/{id}/test`) | Generic DB/connection failures are returned verbatim as `detail=str(exc)`. Driver errors can embed DSN details (host/port/service/username) — **never the password**, but infra metadata leaks to the caller. Low impact on an internal tool; matters before the networked/multi-tenant Phase 7. | Point a profile at an unreachable host → `POST /execute` → 400 detail contains the host/DSN from the oracledb error. | Return a generic "Database error — see server logs" to the client; log the detail server-side (audit already records `reason="execution_error"`). |
| **R1** | S4 | Robustness — durability/concurrency | `src/core/reports.py:223-227`, `230-238`; mirrors `src/core/profiles.py:132-136` | `_save_locked` does a **non-atomic** truncate+write (`open(w)` then `json.dump`) — a crash mid-write can corrupt `reports.json`/`profiles.json`. The `threading.Lock` is per-instance, so **multiple processes/workers** (e.g. Render/Docker with >1 worker) read-modify-write the whole file with no file lock → lost updates / duplicate names / torn file. Acknowledged "single process" in the store docstring; multi-tenant/networked is gated to Phase 7. | Two concurrent workers each `create` a report → last-writer-wins loses one; kill the process during `_save_locked` → truncated JSON → subsequent `list/get` 500s. | Write to a temp file + `os.replace` for atomicity; before Phase 7 add a file lock or move to SQLite. Track in risk register against the existing Phase-7 gate. |
| **R2** | S4 | Robustness — legacy migration | `src/core/reports.py:188-201` (`_deserialize`) | A v2 record that fails `Report(**rec)` validation raises uncaught → 500 on `list/get`. Any dict **missing `id`/`name`** is treated as legacy and migrated using its map key as the report name — a partially-written v2 record could be silently mis-migrated. | Hand-edit `reports.json` to a v2 record missing `name` → it is re-created as a legacy report named after its id key. | Distinguish "legacy shape" from "corrupt v2" explicitly; on validation error, skip+log the record rather than 500. Add a malformed-store test. |

---

## 3. Blocking items

**None.** Per the [gate](../process/external-review-gate.md), the default blocking set is all open **S1/S2**; this review found none, so Phase 4 may close as `PASS-WITH-FIXES`.

**Owner decision required on F1 (the one judgment call):** if "SELECT-only ⇒ no side effects / no writes" is marketed as a *hard product guarantee* (not best-effort), F1 should be **elevated to S2 and gated** until the read-only-account precondition is documented and (optionally) a function denylist lands — because a parse-based allowlist cannot deliver that guarantee alone. If the guarantee is understood as "the *tool* issues only SELECTs, under a least-privilege account," F1 stays S3. I recommend at minimum landing the **documented read-only-account precondition** this phase.

Per gate DoD #4, S3 items (F1–F3, F5, F6) should be fixed **or** formally deferred with rationale in the [issue log](../issue-log.md); F4/R1/R2 (S4) → backlog (R1 against the existing Phase-7 multi-tenant gate).

---

## 4. QA results

| Case | Input | Expected | Observed | Outcome |
|------|-------|----------|----------|---------|
| Automated suite | `pytest -q` | green | **118 passed**, 1 deprecation warning | ✅ matches HANDOFF |
| SQL attack matrix (33 cases) | stacked `;`, DDL, DML, MERGE, `INSERT…RETURNING`, anon `BEGIN/DECLARE`, CTAS, comment-hidden DML, `FOR UPDATE[ OF]`, `UNION…FOR UPDATE`, PG `WITH…DELETE` | every write/PL-SQL/stacked/lock rejected | all 18 dangerous cases **blocked**; benign SELECT/CTE/subquery/union allowed | ✅ |
| Side-effecting function | `SELECT DBMS_LOCK.SLEEP(1) FROM dual` | (probe) | **allowed** | ⚠️ → F1 |
| `SELECT … INTO` | `SELECT x INTO y FROM emp` | reject (fail-closed) | **allowed** | ⚠️ → F2 |
| DML + binds | `POST /execute {sql:"DELETE … :id", binds:{id:1}}` | 400 | `400` "received a DELETE statement" | ✅ |
| Bind value is inert | `binds={n:"'; DROP TABLE emp; --"}` | carried as value, SQL unchanged | `cur.execute(sql, {n:…})`, SQL text unchanged | ✅ |
| Unknown-param smuggling | `POST /reports/{id}/run {binds:{org_id:1, evil:"x"}}` | 400 | `400` "Unknown parameter(s): evil." | ✅ |
| number-param NaN | `POST /reports/{id}/run {binds:{org_id:"nan"}}` | clean reject | `200`, bound value `nan` | ❌ → F3 |
| Password in response | `POST /profiles` then `GET /profiles/{id}` | no password | absent in body + OpenAPI `ProfilePublic` | ✅ |
| Secret in diff | `git diff 3f6c03e..HEAD` grep | none | none | ✅ |
| Audit content | inspect `audit_execution` | hash+metadata only | `sql_sha256[:16]`, no raw SQL/creds | ✅ |
| `max_rows` widen attempt | `max_rows` > global (1000) | clamped to global | `max(1, min(req,1000))` | ✅ |
| Chokepoint uniqueness | grep `.execute(`/`connect` | one gated path | 1× `cur.execute` (db.py:137), 1× connect (db.py:109) | ✅ |
| Contract — `/execute` both targets | `{profile_id, connection}` both set | doc says 422 | accepted, profile wins | ❌ → F4 |
| Manual-conn save | UI sidebar Save | encrypted at rest | plaintext `connection.json` | ⚠️ → F5 |

**Contract integrity:** `/reports` CRUD, `/reports/{id}/run`, `/templates`, and `/execute` `binds` response/error shapes match [05-api-contracts.md](../05-api-contracts.md) (v1.2) — except the `/execute` "both targets → 422" claim (F4). Governed docs (02–06, ADR-007/008, charter, CHANGELOG, tracker, traceability) are in the same change set — DoD #2 satisfied.

**Graceful-failure spot check:** empty SQL, unknown profile (404), unknown report (404), no connection target (400), bad/missing bind (400), unknown param (400), duplicate name (409) all return clean structured errors with no stack trace to the user. The only leak surface is verbatim driver errors on a genuine DB failure (F6).

---

## 5. Could-not-verify

- **Live Oracle execution** — no DB available; all execution paths exercised against a mocked cursor/connection. Not verified against a real instance: server-side `call_timeout` enforcement, `truncated` look-ahead under real result sets, and the actual runtime behaviour of F1 (autonomous-txn function), F2 (`SELECT INTO` erroring), and F3 (NaN bind to NUMBER). Covered by the existing **RISK-04 pre-GA live-Oracle pass**.
- **Live Streamlit click-through** — `test_app_smoke.py` (import/render smoke) is green, but I did not run an interactive session. The Phase-2 `StreamlitDuplicateElementId` class of bug: a static scan of `src/app.py` widget `key=`s found them distinct (report-param keys are `repparam_{report.id}_{name}`; section keys are unique), but a full click-through of the new left-nav (Reports/Templates) remains for the RISK-04 manual UI pass.
- **Multi-process durability (R1)** — reasoned from code, not reproduced; needs a concurrent-workers harness. Gated to Phase 7.

---

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| r1 | 2026-06-10 | Independent reviewer | Initial Phase-4 adversarial review + QA over `3f6c03e..HEAD`. Verdict: PASS-WITH-FIXES (no S1/S2; F1 flagged for owner severity decision). |
