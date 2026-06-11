# Phase 6.5 — Review Package (input to the independent gate)

> **Prepared:** 2026-06-11 · For: owner-supplied independent reviewer · Gate: [external-review-gate](../process/external-review-gate.md)
> Hand the **filled Context block** below (plus this package) to the reviewer along with the [Adversarial Review & QA Prompt](../process/adversarial-reviewer-prompt.md). The reviewer (a fresh-context agent, **not** the author) writes findings to `docs/reviews/phase-6.5-review-r1.md`.

## Change set
- **Full range:** `2ba0a56..d34658c` — 9 commits (3 docs-only: charter `cd0bbfa`, decisions
  `13e7928`, design `30f6194`; 5 build commits B1…B5; 1 doc sweep B6 `d34658c`).
  This package commit (R6.5.1) lands after `d34658c` — a literal `git diff 2ba0a56..HEAD`
  is +1 doc commit over the stated range.
- **Diff:** `git diff 2ba0a56..d34658c` (31 files, +1574/−118).
- **Primary new/changed code:**
  - `src/core/auth.py` (new) — opt-in `require_api_key` dependency: `X-API-Key` vs env
    `APP_API_KEY` (`hmac.compare_digest`); no-op when unset; `/health` exempt.
  - `src/api.py` — app-level auth dependency; `_cors_config()` (`ALLOWED_ORIGINS` env,
    localhost default, `"*"` forfeits credentials); `/nl2sql` catch-all split
    (`ValueError`/`LLMError` verbatim, else generic + `error_id`); profiles
    `SecretConfigError` 500 breadcrumb; API v2.2.0.
  - `src/core/llm/providers.py` — `_parse_inet_component` + `_numeric_host_to_ipv4`
    (ASCII-strict `inet_aton` decode) wired into `validate_base_url`; all-numeric invalid
    hosts rejected fail-closed.
  - `src/core/fileio.py` (new) — `atomic_write_json` (same-dir temp + fsync + `os.replace`),
    adopted by `storage.py`, `core/profiles.py`, `core/reports.py`, `core/schema_store.py`.
  - `src/core/reports.py` / `core/profiles.py` / `core/schema_store.py` — corrupt-record
    **quarantine**: skip-and-log (once per process, `error_id`, record key + exc type only),
    **preserve verbatim on save** (`setdefault` merge), incl. through the report store's
    legacy-migration save.
  - `src/core/errors.py` — `GENERIC_NL2SQL_DETAIL`, `log_error_for_ui` (verbatim-message ref
    for the UI).
  - `src/app.py` — four `SecretConfigError` arms show `(ref: <id>)` via `log_error_for_ui`.
- **Commits:** `cd0bbfa` charter · `13e7928` decisions · `30f6194` design · `8424eb8` **B1**
  (auth+CORS, **ITM-009**) · `3016b87` **B2** (base_url encodings, **ITM-010**) · `e7a978a`
  **B3** (atomic writes, **ITM-013**) · `8e2021d` **B4** (quarantine, **ITM-014**) ·
  `b911972` **B5** (non-DB surfaces, **ITM-017**) · `d34658c` **B6** (doc sweep + closures).

## Filled Context block (paste into the adversarial prompt)
- **Phase under review:** Phase 6.5 — Pre-Deployment Hardening (carried preconditions).
- **Charter:** [charters/phase-6.5-charter.md](../charters/phase-6.5-charter.md) · **Design:**
  [pre-deployment-hardening-design.md](../pre-deployment-hardening-design.md) (note the v1.2
  §4.6 build refinement) · **ADRs:** [ADR-013](../adr/ADR-013-network-edge-hardening.md),
  [ADR-014](../adr/ADR-014-file-store-durability.md).
- **Change set:** `2ba0a56..d34658c`.
- **Phase-specific invariants to attack (in addition to the standing list in the prompt):**
  1. **The chokepoint is untouched.** `git diff 2ba0a56..d34658c -- src/db.py
     src/core/sql_safety.py` must be empty; still exactly one `oracledb.connect` and one
     `cur.execute` in `db.py`. Hardening is edge/storage/error plumbing only.
  2. **Auth default-off is airtight.** With `APP_API_KEY` unset/empty, behaviour must be
     byte-identical to Phase 6 (the whole pre-existing suite runs env-unset). **Attack:** look
     for any way an empty-but-set value (`""`, whitespace) or env mutation mid-process changes
     enforcement surprisingly; confirm the dependency runs on **every** route (incl. ones added
     later via decorators after app creation) and that `/health` is the **only** exemption.
  3. **Auth enabled cannot be bypassed.** With `APP_API_KEY` set: every endpoint except
     `/health` must 401 without/with-wrong key — try method variations, path tricks
     (`//health`, `/health/`, case, URL-encoding) against `EXEMPT_PATHS` exact-match semantics;
     try header-name casing; confirm CORS preflight `OPTIONS` is answered by the middleware,
     not an unauthenticated route handler; confirm the 401 carries the uniform envelope and no
     timing/length oracle beyond `compare_digest`. **No key material in any log line.**
  4. **CORS invariant.** `"*"` + `allow_credentials=True` must be unrepresentable through any
     `ALLOWED_ORIGINS` value (e.g. `"*, https://x"`, whitespace, empty string, trailing
     commas). Confirm the default is the documented localhost pair.
  5. **SSRF encodings (ITM-010).** `validate_base_url` must reject loopback/private/
     link-local/metadata in **every** encoding: decimal/hex/octal integers, dotted hex/octal,
     2/3-group short forms, mixed-base groups. **Attack the decoder itself:** Unicode digits,
     underscores (`1_0`), `0x` with empty digits, >4 groups, values > 2³²−1, negative signs,
     IPv6 forms, IDNA tricks. An all-numeric host that isn't valid IPv4 must be **rejected**,
     not passed to DNS; real digit-leading hostnames (`1password.com`) must still pass.
     DNS-rebinding is the accepted residual (RISK-11) — confirm nothing else regressed.
  6. **Atomic writes (ITM-013).** All four stores write via `atomic_write_json`; grep the diff
     for any surviving direct `open(..., "w")+json.dump` store write. **Attack:** force
     `json.dump` to fail mid-write (unserializable payload) — the target must keep its previous
     complete content and no temp file may remain; verify the on-disk shape (indent,
     `default=str` for reports) is unchanged vs Phase 6.
  7. **Quarantine semantics (ITM-014).** A corrupt v2 **or** legacy record: never a 500 on
     `list`/`get`; not served (`get`/`update`/`delete` → not-found); logged with `error_id`
     and **only** the record key + exception type (never the record body/SQL); **preserved
     verbatim across every save**, including the report store's in-place migration save.
     **Attack:** craft records that are dicts-with-id/name-but-invalid, non-dicts, nested
     junk; check a create/update/delete cycle never drops the quarantined raw record; check
     the quarantine state can't go stale across same-instance loads (lock held?).
  8. **ITM-017 classification.** `/nl2sql`: intentional `ValueError`/`LLMError` text verbatim
     (e.g. "Schema is empty…"), **any other** exception → generic
     `"Could not generate SQL — see server logs."` + `error_id`, full text server-side keyed by
     the same id. **Attack:** raise exceptions embedding host/DSN/key-looking text from inside
     the generation path and confirm nothing leaks in body or headers. Profiles
     `SecretConfigError` 500: verbatim + a server-side breadcrumb keyed to the body's
     `error_id`. UI `SecretConfigError` arms show `(ref: <id>)`.
  9. **No regression** to the standing invariants — SELECT/CTE-only, AI-proposes-never-runs,
     binds-as-values (ADR-007), secrets-via-env, metadata-only persistence, ITM-015
     DB-sanitization, correlation-id sanitization (F-3) — none weakened by the new edge or
     storage code.

## Test status
- `pytest -q` → **236 passed** locally (mocked DB throughout — no live Oracle/LLM calls; auth
  tests set/unset `APP_API_KEY` via monkeypatch).
- New/extended suites: `test_auth.py` (16) · `test_llm_providers.py` (+17 encoding matrix) ·
  `test_fileio.py` (7) · `test_store_robustness.py` (6) · `test_error_handling.py` (+5
  ITM-017) — **+51** over Phase 6's 185.
- Run: `pip install -r requirements-dev.txt` then `APP_SECRET_KEY=… PYTHONPATH=. pytest -q`.
  CI runs the matrix on **Python 3.11 + 3.13** (push to demonstrate post-review, per ITM-016
  precedent: green must be *shown*, not asserted).

## Known limitations / not covered (verify or flag)
- **No live Oracle** (standing pre-GA RISK-04) — unchanged by this phase.
- **Single shared API key, not identity:** no users/roles/sessions/rate limiting (charter
  scope-out); enabling auth is operator discipline (`APP_API_KEY` must be set before any
  networked exposure — D7 §2 rule). The reviewer should judge whether default-off is
  acceptable given it preserves the local posture and D7 documents the rule.
- **Multi-worker concurrency deliberately unsolved** (charter D-D): one worker per store
  directory is the documented constraint; only crash-durability was in scope.
- **DNS-rebinding** for `base_url` remains the accepted RISK-11 residual.
- **Crash-during-write is simulated** (failing serializer), not a real kill-mid-`os.replace`;
  the atomicity argument rests on same-volume `os.replace` semantics.
- **UI** verified via headless `AppTest` only (no browser/visual pass).

## Expected reviewer output
Verdict (`PASS` / `PASS-WITH-FIXES` / `FAIL`), findings table (severity + exact `file:line` + repro), blocking list (default: open S1/S2), QA results, could-not-verify — saved to `docs/reviews/phase-6.5-review-r1.md`.
