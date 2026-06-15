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

## Decision
A **conservative, LLM-signaled refusal**, layered on top of (never replacing) the chokepoint:

1. **Prompt.** `SYSTEM_PROMPT` instructs the model: if the request is **not answerable from the provided
   schema** (small talk, general knowledge, unrelated topics), respond with a single line
   `CANNOT_ANSWER: <one short sentence>` and nothing else — *only* when clearly off-topic; if plausibly a
   data question, attempt the SQL.
2. **Generator** (`src/nl2sql.py`). Detects the sentinel **only when there is no SQL fence** (if the model
   returns both, prefer the SQL — never block a real question) and returns
   `NLSQLResult(sql="", answerable=False, message=<reason>)`.
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
  "how to swim" → declined, "headcount by department" → SQL. The chokepoint is the backstop regardless.

## Alternatives considered
- **Heuristic pre-filter (no LLM):** rejected — can't judge relevance to a schema without the model.
- **Post-hoc SQL relevance check:** rejected — the model can produce plausible SQL against real tables for
  an off-topic prompt; unreliable to detect.
- **Confidence-threshold blocking:** rejected — the heuristic confidence isn't a reliable relevance signal
  and would cause false rejects.
