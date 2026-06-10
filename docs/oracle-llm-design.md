# LLM Design — NL→SQL 2.0 & Provider Abstraction (Phase 3)

> **Document:** LLM Design · **Version:** 1.0 · **Status:** Proposed (awaiting approval to build) · **Owner:** Engineering · **Last updated:** 2026-06-10
> Implements the [Phase 3 charter](charters/phase-3-charter.md). Decisions D-A…D-E are resolved there.

## 1. Goals
Make NL→SQL **provider-agnostic** and **explainable**, with **strict redaction** to external LLMs, building on the Phase-2 `LLMConfig`. AI still only *proposes* SQL; the central safety layer and "review before run" are unchanged.

## 2. Provider abstraction

```
src/core/llm/
  base.py        # LLMProvider (Protocol), LLMResult, LLMError
  providers.py   # ExternalLLMProvider (OpenAI-compatible: Groq/OpenAI), LocalLLMProvider (stub)
  policy.py      # LLM_POLICY resolution + provider selection
  redaction.py   # build_external_context() + assert_no_values()
  confidence.py  # heuristic High/Medium/Low
```

```python
class LLMProvider(Protocol):
    name: str
    def is_available(self) -> bool: ...
    def complete(self, system: str, user: str, model: str | None) -> str: ...

class ExternalLLMProvider:   # Groq or OpenAI, chosen by LLMConfig.base_url/provider
    ...
class LocalLLMProvider:      # seam for OCI / Oracle 23ai — stub for now
    def is_available(self) -> bool: return False
    def complete(self, *a, **k): raise LLMError("Local LLM provider not configured yet.")
```

`nl2sql.py` is refactored to obtain a provider from `policy.select_provider(LLMConfig)` instead of building an OpenAI client directly. Existing per-user `LLMConfig` (Phase 2) is reused unchanged.

## 3. Policy toggle (D-E)
`LLM_POLICY` env, default `local_external`:
- `local_only` → only `LocalLLMProvider` (currently unavailable → clear "not configured" error).
- `local_external` → prefer Local if available, else External.
- `external_disabled` → never call External; if Local unavailable, NL→SQL returns a clear, graceful "disabled" message (no crash).

## 4. Redaction (D-D, strict) — the critical control
- External prompts contain **only** `schema.to_compact_markdown()` (table/column/type/FK names + relationships) — which already carries **no row values**.
- Plus the user's own NL question text (their intent). **No result rows, no sample values, no schema sample data, no raw identifiers** are ever added.
- `redaction.assert_no_values(prompt, schema)` is called before any External send and raises if disallowed content is detected (defense-in-depth); covered by tests.
- **Documented nuance:** the user's free-text question is sent to the selected provider. Tenants who must not send question text externally set `LLM_POLICY=external_disabled`. (Local/in-DB providers, when added, may receive richer context.)

## 5. Explanation (D-B)
- Single provider call requests fenced SQL **plus** a short `Explanation:` paragraph; parsed robustly (fall back to SQL-only if the explanation block is missing).
- System prompt instructs: explain using only the provided schema; no invented tables/columns; ≤ 3 sentences.

## 6. Confidence (D-A, deterministic heuristic)
Computed **after** generation, from signals we control (no LLM self-rating):
1. SQL parses as a safe SELECT (already validated by `core.sql_safety`).
2. Fraction of referenced tables/columns (extracted from the sqlglot AST) that exist in the uploaded schema.
3. Whether JOINs use known relationships.

Mapping: **High** = parses + all identifiers resolved + joins known; **Medium** = parses + minor gaps; **Low** = unresolved identifiers or unknown joins. Returns `{level, reasons[]}` (e.g., "column INVOICE_DT not found in schema"). Explicitly **not** a correctness guarantee.

## 7. Output contract changes
- `generate_sql_from_nl(...)` → returns `NLSQLResult(sql, explanation, confidence)`.
- `POST /nl2sql` response: `{ sql, explanation, confidence: { level, reasons[] } }` (additive; `sql` unchanged). Updates **D5 API Contracts**, **D4 Data Models**, **D3 Architecture**.
- UI (Query Builder): show proposed SQL and explanation side-by-side, with the confidence chip; SQL stays editable; run still goes through the safety chokepoint.

## 8. Graceful degradation
Missing/invalid key, unavailable provider, or policy-blocked → a clear user-facing message and HTTP 400 (API) / inline error (UI). Never a stack trace; never a crash.

## 9. Test plan (must pass + feed the gate)
- **Redaction:** external context for a sample schema contains no row values; `assert_no_values` rejects a prompt seeded with data; question text passes.
- **Policy/provider:** `external_disabled` never instantiates External; `local_only` with stub → clear error; `local_external` selects External when Local unavailable.
- **Confidence:** schema + SQL referencing existing columns → High; referencing a missing column → Low (with reason).
- **Explanation parsing:** mocked provider output → sql + explanation extracted; missing-explanation fallback.
- **Graceful degradation:** missing key → clear message, no crash.
- **Safety regression:** generated SQL still rejected if not a safe SELECT.
- All network-touching tests use a mocked provider (no live calls in CI).

## 10. Exit gate
On completion: tests green in CI, governed docs updated, then **independent adversarial review + QA (owner-supplied reviewer) → PASS** per [the gate](process/external-review-gate.md).

## Revision history
| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Engineering | Proposed design from resolved Discovery decisions. |
