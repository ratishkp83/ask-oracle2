# ADR-025 — Off-topic / out-of-scope NL guard (decline non-data questions)

- **Status:** Accepted
- **Date:** 2026-06-15
- **Deciders:** Product/Engineering (owner-requested)
- **Phase:** v2 / Phase 9 (post-B7 hardening)

## Context
`generate_sql_from_nl` always asked the model for a `SELECT`; the only guard was the SELECT-only safety
check. So an off-topic prompt like **"how to swim"** still produced a query against the schema, which then
**ran** — immediately under **Auto-run** ([ADR-022](ADR-022-auto-run-mode.md)), or on approval. There was
no notion of "this isn't a question about the data." The owner asked that such requests be **ignored with
a friendly notice** instead of fabricating and running SQL.

A second manifestation surfaced in testing: **"what is count of woman"** against a schema with **no gender
column** produced a fabricated proxy (`WHERE SUBSTR(EMAIL, LENGTH(EMAIL)-1, 1) = 'a'`) and ran it — a
data-*shaped* question that needs a column the schema lacks. The guard must also cover this: decline rather
than invent a proxy / substitute a different metric.

## Decision
A **conservative, LLM-signaled refusal**, layered on top of (never replacing) the chokepoint:

1. **Prompt.** `SYSTEM_PROMPT` instructs the model to use **only tables/columns that exist** and to
   **never invent a column or fabricate a proxy** for a concept the schema doesn't contain. It responds
   `CANNOT_ANSWER: <one short sentence>` (and nothing else) in either case: (a) the request isn't about the
   data at all (small talk / general knowledge), or (b) answering needs information the schema lacks (e.g.
   counting "women" with no gender column) — decline, don't substitute a different metric. Otherwise, if it
   maps to existing tables/columns, attempt the SQL.
2. **Generator** (`src/nl2sql.py`). Detects the sentinel **only when there is no SQL fence** (if the model
   returns both, prefer the SQL — never block a real question) and returns
   `NLSQLResult(sql="", answerable=False, message=<reason>)`.
   **Consistency (BUG-012):** the model declines in many shapes — the sentinel, plain prose, or an
   unparseable / non-SELECT reply. **All** of them now resolve to the *same* graceful
   `answerable=False` notice. The generator no longer raises the technical
   *"Generated SQL is not a SELECT/CTE. Aborting for safety."* to the user; any non-safe-SELECT generation
   is logged server-side (`ask_oracle` logger) and returned as a not-answerable result (prose carries its
   reason; a SQL-shaped non-SELECT gets a generic message). The **`/execute` chokepoint stays the hard
   safety boundary** — nothing non-SELECT can ever run regardless.
3. **Contract.** `NLSQLResult` + `POST /nl2sql` gain `answerable: bool` (default **True**) and
   `message: str|null` — additive, so older clients/responses keep working.
4. **UI.** When `answerable === false`, the Ask page shows a calm `role="status"` notice ("I can only
   answer questions about your Oracle data") and **proposes/runs nothing — including under Auto-run** (the
   chokepoint is never reached).

## Rationale / Security
- **Additive gate, not a loosening.** The SELECT-only chokepoint ([ADR-005](ADR-005-execute-chokepoint.md))
  remains the hard safety control; this only *reduces* irrelevant/auto-run executions.
- **Conservative by design.** Refuse only clear off-topic input; when unsure, fall through to SQL — so a
  real but oddly-phrased question is never blocked. The "prefer SQL if both fence and sentinel" rule is a
  second guard against false refusals.
- The refusal path returns **no SQL**, so it adds no execution surface.

## Consequences
- Off-topic prompts get a friendly notice instead of a bogus result; fewer wasted live runs.
- Small, defaulted contract addition (`answerable`, `message`).
- Depends on model compliance with the sentinel instruction; verified live (Groq `llama-3.3-70b`) —
  "how to swim" → declined, **"count of women" → declined** ("no column … to determine gender"; no proxy),
  and "count of employees" / "headcount by department" / "average salary" → SQL. The chokepoint is the
  backstop regardless.

## Alternatives considered
- **Heuristic pre-filter (no LLM):** rejected — can't judge relevance to a schema without the model.
- **Post-hoc SQL relevance check:** rejected — the model can produce plausible SQL against real tables for
  an off-topic prompt; unreliable to detect.
- **Confidence-threshold blocking:** rejected — the heuristic confidence isn't a reliable relevance signal
  and would cause false rejects.
