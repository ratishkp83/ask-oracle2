# Phase 3 Charter — NL→SQL 2.0 & LLM Abstraction

> **Document:** Phase Charter · **Version:** 1.1 · **Status:** Discovery complete → Design (proposed) · **Owner:** Product/Engineering · **Last updated:** 2026-06-10

## Lifecycle stage
**Discovery complete** (decisions resolved below). Design proposed in [oracle-llm-design.md](../oracle-llm-design.md); **Development begins on owner approval of the design.**

## Objectives
Turn the existing NL→SQL into a **provider-agnostic, explainable** module, and enforce prompt redaction so external LLMs never receive live data or PII/PHI. Builds on the Phase-2 `LLMConfig` seed.

## Scope — in
- `LLMProvider` interface with concrete providers (Groq, OpenAI via the OpenAI-compatible client) and a **stub** `LocalLLMProvider` seam for OCI/23ai.
- NL→SQL output = **proposed SQL + short explanation (+ confidence)**; still verified by the central safety layer and never auto-executed.
- **Redaction policy**: only schema metadata in prompts; no live data, no raw customer identifiers/PII/PHI to external providers by default.
- **Policy toggle**: Local only / Local + External / External disabled.
- UI: show proposed SQL and explanation side-by-side.

## Scope — out
- Live OCI / Oracle 23ai integration implementation (interface + stub only; full build is Phase 7).
- Authentication / multi-tenant identity (LLM config remains per-session).

## Deliverables
- Refactored `/nl2sql` behind the provider abstraction; explanation (+confidence) in the response.
- `docs/oracle-llm-design.md` (governed): prompt strategy, redaction rules, provider design.
- UI update; tests; updated API contract (D5), data models (D4), architecture (D3), and ADRs.

## Risks
| Risk | Severity | Mitigation |
|------|----------|------------|
| Redaction failure → PII/PHI leaks to an external LLM | **Critical** | Strict default policy + automated redaction tests; deny live data/raw IDs by construction |
| LLM self-rated confidence is miscalibrated/misleading | Medium | Prefer a deterministic heuristic; label coarsely; never imply correctness guarantee |
| Provider misconfiguration (missing key) | Medium | Graceful degradation with a clear message; tested |
| Explanation latency/cost | Low | Keep explanations short; make optional |

## Success criteria (phase exit)
1. ≥2 providers pluggable behind one interface, switchable by config; `LocalLLMProvider` seam present.
2. Redaction enforced **and tested**: no live data / raw IDs in external prompts by default.
3. Graceful degradation on misconfiguration (tested).
4. NL→SQL returns SQL + explanation (+ confidence) and still passes the safety layer.
5. Tests green in CI; governed docs current.
6. **Independent adversarial review + QA returns PASS** ([gate](../process/external-review-gate.md)); **reviewer agent supplied by the product owner**.

## Decisions (resolved 2026-06-10)
- **D-A — Confidence:** **deterministic heuristic** → coarse High/Medium/Low from schema coverage, parse success, and identifier resolution. No LLM self-rating.
- **D-B — Explanation guardrails:** short rationale referencing only schema elements already shown; no data; (low risk since prompts carry no values).
- **D-C — Provider set v1:** **Groq + OpenAI concrete** via the OpenAI-compatible client; **`LocalLLMProvider` as a stub seam** for OCI/23ai.
- **D-D — Redaction default:** **strict** — external prompts carry table/column/type names + relationships only; **never** sample/live values or raw identifiers. Local/in-DB providers may receive more (future).
- **D-E — Policy toggle:** `LLM_POLICY` env (`local_only` / `local_external` / `external_disabled`), default `local_external`; per-user later.

## Revision history

| Version | Date | Author | Change |
|---------|------|--------|--------|
| 1.0 | 2026-06-10 | Product/Eng | Discovery charter opened. |
