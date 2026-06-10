"""Provider-agnostic, explainable NL→SQL building blocks (Phase 3).

Public surface:
- `LLMConfig`, `LLMProvider`, `LLMResult`-style `NLSQLResult`, `Confidence`, `LLMError` (base)
- `ExternalLLMProvider`, `LocalLLMProvider` (providers)
- `select_provider`, `get_policy` (policy)
- `build_external_context`, `assert_no_values`, `RedactionError` (redaction)
- `assess_confidence` (confidence)
"""
