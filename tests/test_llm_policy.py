"""Policy tests — LLM_POLICY toggle and provider selection / graceful errors."""

import pytest

from src.core.llm.base import LLMConfig, LLMError
from src.core.llm.policy import get_policy, select_provider


def test_default_policy(monkeypatch):
    monkeypatch.delenv("LLM_POLICY", raising=False)
    assert get_policy() == "local_external"
    monkeypatch.setenv("LLM_POLICY", "bogus")
    assert get_policy() == "local_external"


def test_external_disabled_raises_when_no_local(monkeypatch):
    monkeypatch.setenv("LLM_POLICY", "external_disabled")
    with pytest.raises(LLMError):
        select_provider(LLMConfig(api_key="sk-test"))


def test_local_only_raises_with_stub(monkeypatch):
    monkeypatch.setenv("LLM_POLICY", "local_only")
    with pytest.raises(LLMError):
        select_provider()


def test_local_external_selects_external(monkeypatch):
    monkeypatch.setenv("LLM_POLICY", "local_external")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk-env")
    provider = select_provider()
    assert provider.name == "external" and provider.is_available()


def test_local_external_raises_when_no_keys(monkeypatch):
    monkeypatch.setenv("LLM_POLICY", "local_external")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(LLMError):
        select_provider(LLMConfig())
