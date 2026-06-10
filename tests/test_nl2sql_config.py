"""Tests for per-user LLM configuration resolution (no network calls)."""

from src.nl2sql import (
    DEFAULT_GROQ_MODEL,
    DEFAULT_OPENAI_MODEL,
    GROQ_BASE_URL,
    LLMConfig,
    _client_from_config,
    resolve_model,
)


def test_explicit_model_wins():
    assert resolve_model(LLMConfig(model="my-custom-model")) == "my-custom-model"


def test_provider_groq_default_model(monkeypatch):
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    assert resolve_model(LLMConfig(provider="groq")) == DEFAULT_GROQ_MODEL


def test_provider_openai_default_model(monkeypatch):
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    assert resolve_model(LLMConfig(provider="openai")) == DEFAULT_OPENAI_MODEL


def test_per_user_groq_key_sets_base_url():
    client = _client_from_config(LLMConfig(provider="groq", api_key="sk-test"))
    assert str(client.base_url).rstrip("/") == GROQ_BASE_URL


def test_per_user_openai_uses_default_base_url():
    client = _client_from_config(LLMConfig(provider="openai", api_key="sk-test"))
    assert "openai.com" in str(client.base_url)


def test_falls_back_to_env_when_no_user_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk-env")
    client = _client_from_config(None)
    assert str(client.base_url).rstrip("/") == GROQ_BASE_URL
