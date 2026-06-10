from __future__ import annotations

import os
from typing import Optional, Tuple

from openai import OpenAI

from src.core.llm.base import LLMConfig, LLMError

# Groq is OpenAI-API-compatible; we point the same client at its base URL.
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "llama3-70b-8192"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


class ExternalLLMProvider:
    """OpenAI-compatible external provider (Groq or OpenAI).

    Resolution order for credentials: an explicit per-user `LLMConfig.api_key`,
    else `GROQ_API_KEY`, else `OPENAI_API_KEY` from the environment.
    """

    name = "external"

    def __init__(self, config: Optional[LLMConfig] = None):
        self._config = config or LLMConfig()
        self._client, self._label = self._build_client()

    def _build_client(self) -> Tuple[Optional[OpenAI], Optional[str]]:
        cfg = self._config
        if cfg.api_key:
            provider = (cfg.provider or "").lower()
            base_url = cfg.base_url or (GROQ_BASE_URL if provider == "groq" else None)
            if base_url:
                return OpenAI(api_key=cfg.api_key, base_url=base_url), (provider or "openai")
            return OpenAI(api_key=cfg.api_key), (provider or "openai")
        groq_key = os.getenv("GROQ_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        if groq_key:
            return OpenAI(api_key=groq_key, base_url=GROQ_BASE_URL), "groq"
        if openai_key:
            return OpenAI(api_key=openai_key), "openai"
        return None, None

    def is_available(self) -> bool:
        return self._client is not None

    def resolve_model(self, requested: Optional[str] = None) -> str:
        if requested:
            return requested
        if self._config.model:
            return self._config.model
        if self._label == "groq":
            return os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
        return os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)

    def complete(self, system: str, user: str, model: Optional[str] = None) -> str:
        if self._client is None:
            raise LLMError(
                "No external LLM key configured. Set GROQ_API_KEY or OPENAI_API_KEY, "
                "or supply a key in Settings."
            )
        completion = self._client.chat.completions.create(
            model=self.resolve_model(model),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.1,
        )
        return (completion.choices[0].message.content or "").strip()


class LocalLLMProvider:
    """Seam for a local / in-database provider (OCI, Oracle 23ai). Stub for now."""

    name = "local"

    def is_available(self) -> bool:
        return False

    def resolve_model(self, requested: Optional[str] = None) -> str:
        return requested or "local"

    def complete(self, system: str, user: str, model: Optional[str] = None) -> str:
        raise LLMError("Local LLM provider (OCI / Oracle 23ai) is not configured yet.")
