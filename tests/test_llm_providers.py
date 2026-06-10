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


# F4 — user-supplied base_url SSRF guard.
def test_base_url_private_ip_rejected():
    with pytest.raises(LLMError):
        ExternalLLMProvider(LLMConfig(provider="openai", api_key="x", base_url="https://169.254.169.254/v1"))


def test_base_url_requires_https():
    with pytest.raises(LLMError):
        ExternalLLMProvider(LLMConfig(provider="openai", api_key="x", base_url="http://example.com/v1"))


def test_base_url_public_https_ok():
    p = ExternalLLMProvider(LLMConfig(provider="openai", api_key="x", base_url="https://api.example.com/v1"))
    assert p.is_available()


# F6 — api_key must not appear in repr.
def test_llmconfig_repr_hides_key():
    assert "sk-SECRET" not in repr(LLMConfig(api_key="sk-SECRET"))
