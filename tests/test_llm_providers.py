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


# ITM-010 (Phase 6.5 B2) — inet_aton-style numeric encodings of internal
# addresses must be rejected like their dotted-quad forms.
@pytest.mark.parametrize(
    "host",
    [
        "2130706433",      # decimal integer 127.0.0.1
        "0x7f000001",      # hex integer 127.0.0.1
        "017700000001",    # octal integer 127.0.0.1
        "0x7f.0.0.1",      # dotted hex
        "0177.0.0.1",      # dotted octal
        "127.1",           # two-group short form of 127.0.0.1
        "167772161",       # decimal integer 10.0.0.1
        "0xa9.0xfe.0xa9.0xfe",  # hex 169.254.169.254 (metadata)
    ],
)
def test_base_url_numeric_encodings_of_internal_rejected(host):
    with pytest.raises(LLMError):
        ExternalLLMProvider(LLMConfig(provider="openai", api_key="x", base_url=f"https://{host}/v1"))


@pytest.mark.parametrize(
    "host",
    [
        "4294967296",       # > 2**32-1: not a valid IPv4
        "1.2.3.4.5",        # five groups
        "09.0.0.1",         # leading-zero non-octal group
        "0x.1.2.3",         # empty hex group
        "256.256.256.256",  # byte groups out of range
    ],
)
def test_base_url_all_numeric_but_invalid_rejected(host):
    """An all-numeric host that isn't a valid IPv4 is never a legitimate
    public hostname — rejected fail-closed rather than passed to DNS."""
    with pytest.raises(LLMError):
        ExternalLLMProvider(LLMConfig(provider="openai", api_key="x", base_url=f"https://{host}/v1"))


@pytest.mark.parametrize(
    "host",
    [
        "api.example.com",
        "1password.com",          # digit-leading label, alphabetic TLD
        "365.api.example.com",    # fully numeric label, alphabetic TLD
    ],
)
def test_base_url_real_hostnames_still_pass(host):
    p = ExternalLLMProvider(LLMConfig(provider="openai", api_key="x", base_url=f"https://{host}/v1"))
    assert p.is_available()


def test_base_url_ipv6_loopback_still_rejected():
    with pytest.raises(LLMError):
        ExternalLLMProvider(LLMConfig(provider="openai", api_key="x", base_url="https://[::1]/v1"))


# Review r1/R1 — Unicode compatibility-digit encodings of internal addresses
# must NFKC-fold to ASCII and be rejected at the first-line guard, not slip
# through to a downstream HTTP-client check.
@pytest.mark.parametrize(
    "host",
    [
        "１２７.0.0.1",            # fullwidth first octet, ASCII rest = 127.0.0.1
        "１２７.０.０.１",          # fully fullwidth dotted-quad = 127.0.0.1
        "２１３０７０６４３３",  # fullwidth decimal integer = 2130706433 = 127.0.0.1
    ],
)
def test_base_url_unicode_digit_encodings_rejected(host):
    with pytest.raises(LLMError):
        ExternalLLMProvider(LLMConfig(provider="openai", api_key="x", base_url=f"https://{host}/v1"))


def test_base_url_fullwidth_localhost_rejected():
    # Fullwidth "localhost" folds to the blocked host.
    host = "ｌｏｃａｌｈｏｓｔ"
    with pytest.raises(LLMError):
        ExternalLLMProvider(LLMConfig(provider="openai", api_key="x", base_url=f"https://{host}/v1"))


def test_base_url_genuine_idn_hostname_still_passes():
    # A real internationalized hostname (non-numeric) survives NFKC as a
    # hostname — we fold the encoding, we do not reject non-ASCII outright.
    p = ExternalLLMProvider(LLMConfig(provider="openai", api_key="x", base_url="https://münchen.example.com/v1"))
    assert p.is_available()


# F6 — api_key must not appear in repr.
def test_llmconfig_repr_hides_key():
    assert "sk-SECRET" not in repr(LLMConfig(api_key="sk-SECRET"))
