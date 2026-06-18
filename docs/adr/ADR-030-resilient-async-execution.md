# ADR-030 — Resilient async execution + ephemeral result cache

- **Status:** Proposed (B2 — awaiting owner sign-off)
- **Date:** 2026-06-18
- **Deciders:** Product/Engineering
- **Phase:** v2 / Phase 11 (Pillar 2, B5)

## Context
A genuinely heavy query **times out the synchronous HTTP request** today — `POST /execute` runs `run_select` inline. No amount of better generation eliminates this for legitimately long analytical reports; it must be *contained*. The owner set the retention posture: **ephemeral, memory-only, short TTL** (D-B) — keep our near-zero row-data-at-rest posture. The deployment is single-worker (RISK-16), so the job model must be in-process, not a durable queue.

## Decision
Add an **in-memory async job model** over the **same** chokepoint, with a **hybrid** trigger:

- **`src/core/jobs.py`** — `QueryJob` + `JobStore` (in-memory dict, lock, **TTL eviction**, **max-jobs cap**; nothing on disk) + a bounded `ThreadPoolExecutor` running the existing `_run_sql(...)` body per job.
- **Hybrid `POST /execute` (D-E):** start a job, wait up to `EXECUTE_SYNC_WAIT_SECONDS`; if it finishes, return the result **inline, identical to today** (back-compatible); else return `202 {job_id, state:"running"}`. `GET /execute/jobs/{id}` polls; `POST /execute/jobs/{id}/cancel` cancels.
- **Timeout + cancel:** `run_select` already caps each call via `conn.call_timeout` (the hard backstop); async uses a longer `MAX_EXECUTION_SECONDS_ASYNC`. Explicit cancel hands the live `conn` to the job to call `conn.cancel()` (best-effort, thin-mode).
- **Ephemeral result cache** — `ResultCache` keyed by `hash(sql+binds+profile_id+max_rows)`, in-memory, short TTL, size-capped, per-profile; `_run_sql` consults it before connecting. Opt-out for "force fresh."
- **Sample-first (D-I):** opt-in `SAMPLE(p)` wrap of the approved SQL (still a SELECT through the chokepoint) for a fast **approximate** preview, clearly labelled, with one-click full/async run.
- **Frontend:** `execute()` handles `202` → polls with backoff, showing "Still running… (cancel)"; the cascade fan-out reuses the same path.

## Consequences
- A long query no longer fails — it runs as a job; the user gets progress + cancel. This is the core answer to the owner's timeout pain.
- Repeat queries are instant within the TTL (cache), at the cost of brief staleness — acceptable for a reporting tool, and bounded by a short TTL + force-fresh.
- New server-side state (jobs + cache) is **ephemeral and memory-only** → no persisted row data, consistent with the security posture (P11-R2); it resets on restart (acceptable for beta).
- Cancellation is best-effort; `call_timeout` guarantees runaway queries still stop (P11-R6).

## Security / invariants
- **Invariant 1:** jobs run the same `assert_safe_select`→`run_select` path; async changes *when we wait*, not *what runs*. The sample wrap is a SELECT.
- **Invariant 4:** jobs/cache keyed by `profile_id`; results hold already-authorized data, never credentials; job ids are opaque.
- **Invariant 5:** job failures/timeouts/cancellations surface via `_db_error` with `error_id`; raw text logged server-side.

## Alternatives considered
- **Always-synchronous with a bigger timeout:** rejected — still fails the genuinely long report and ties up a worker.
- **Durable queue (Celery/Redis/DB-backed jobs):** rejected for this phase — over-engineered for a single-worker beta and would persist row data (against D-B). Revisit if/when scheduling (a separate phase) needs durable, unattended execution.
- **Persisted result cache:** rejected for this phase (D-B) — would put row data at rest, requiring encryption + retention review; a deliberate later decision.
