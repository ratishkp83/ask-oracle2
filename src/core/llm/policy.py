from __future__ import annotations

import os
from typing import Optional

from src.core.llm.base import LLMConfig, LLMError, LLMProvider
from src.core.llm.providers import ExternalLLMProvider, LocalLLMProvider

VALID_POLICIES = {"local_only", "local_external", "external_disabled"}
DEFAULT_POLICY = "local_external"


def get_policy() -> str:
    """Resolve the tenant LLM policy from `LLM_POLICY` (default ``local_external``)."""
    value = (os.getenv("LLM_POLICY") or DEFAULT_POLICY).strip().lower()
    return value if value in VALID_POLICIES else DEFAULT_POLICY


def select_provider(config: Optional[LLMConfig] = None, policy: Optional[str] = None) -> LLMProvider:
    """Pick a provider honoring the policy toggle. Raises :class:`LLMError` (clean,
    surfaced to the user) when no permitted provider is available — never crashes.
    """
    policy = policy or get_policy()
    local = LocalLLMProvider()

    if policy == "local_only":
        if local.is_available():
            return local
        raise LLMError("LLM_POLICY=local_only but no local LLM provider is configured yet.")

    if policy == "external_disabled":
        if local.is_available():
            return local
        raise LLMError(
            "External LLMs are disabled (LLM_POLICY=external_disabled) and no local "
            "provider is configured — NL→SQL is unavailable."
        )

    # local_external: prefer a local provider if present, else fall back to external.
    if local.is_available():
        return local
    external = ExternalLLMProvider(config)
    if external.is_available():
        return external
    raise LLMError(
        "No LLM provider available. Set GROQ_API_KEY/OPENAI_API_KEY (or supply a key "
        "in Settings), or configure a local provider."
    )
