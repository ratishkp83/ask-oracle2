"""Provider tests — credential resolution, base URLs, availability, stub."""

import pytest

from src.core.llm.base import LLMConfig, LLMError
from src.core.llm.providers import (
    DEFAULT_GROQ_MODEL,
    DEFAULT_OPENAI_MODEL,
    GROQ_BASE_URL,
    ExternalLLMProvider,
    LocalLLMProvider,
)


def test_external_groq_sets_base_url_and_model(monkeypatch):
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    p = ExternalLLMProvider(LLMConfig(provider="groq", api_key="sk-test"))
    assert p.is_available()
    assert str(p._client.base_url).rstrip("/") == GROQ_BASE_URL
    assert p.resolve_model() == DEFAULT_GROQ_MODEL


def test_external_openai_default_base_url_and_model(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    p = ExternalLLMProvider(LLMConfig(provider="openai", api_key="sk-test"))
    assert "openai.com" in str(p._client.base_url)
    assert p.resolve_model() == DEFAULT_OPENAI_MODEL


def test_external_unavailable_without_key(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    p = ExternalLLMProvider(LLMConfig())
    assert not p.is_available()
    with pytest.raises(LLMError):
        p.complete("system", "user")


def test_external_env_fallback_prefers_groq(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk-env")
    p = ExternalLLMProvider(LLMConfig())
    assert p.is_available()
    assert str(p._client.base_url).rstrip("/") == GROQ_BASE_URL


def test_local_provider_is_stub():
    p = LocalLLMProvider()
    assert not p.is_available()
    with pytest.raises(LLMError):
        p.complete("system", "user")
