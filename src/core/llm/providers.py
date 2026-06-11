from __future__ import annotations

import ipaddress
import os
import string
import unicodedata
from typing import Optional, Tuple
from urllib.parse import urlparse

from openai import OpenAI

from src.core.llm.base import LLMConfig, LLMError

# Groq is OpenAI-API-compatible; we point the same client at its base URL.
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "llama3-70b-8192"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"

_BLOCKED_HOSTS = {"localhost", "metadata.google.internal", "metadata"}


def _parse_inet_component(text: str) -> Optional[int]:
    """Parse one dot-group per C ``inet_aton`` rules: ``0x…`` hex, ``0…`` octal,
    else decimal. ASCII-only on purpose — ``int()`` would accept Unicode digits
    and underscores, which would reopen the encoding bypass. ``None`` = not a
    well-formed numeric group.
    """
    if text[:2].lower() == "0x":
        digits = text[2:]
        if digits and all(c in string.hexdigits for c in digits):
            return int(digits, 16)
        return None
    if len(text) > 1 and text[0] == "0":
        if all(c in "01234567" for c in text):
            return int(text, 8)
        return None
    if text and all(c in string.digits for c in text):
        return int(text)
    return None


def _numeric_host_to_ipv4(host: str) -> Optional[str]:
    """Decode ``inet_aton``-style numeric hosts (ITM-010): decimal/hex/octal in
    1–4 dot-groups (e.g. ``2130706433``, ``0x7f000001``, ``0177.0.0.1``) to the
    canonical dotted-quad.

    Returns ``None`` for a real hostname (any group not ASCII-digit-leading,
    e.g. ``1password.com``). Raises ``ValueError`` for a host that *looks*
    numeric (every group digit-leading) but is not a valid IPv4 — public TLDs
    never start with a digit, so an all-numeric host is never a legitimate
    hostname and is rejected fail-closed.
    """
    groups = host.split(".")
    if not all(g and g[0] in string.digits for g in groups):
        return None  # a hostname, not a numeric address
    if len(groups) > 4:
        raise ValueError("more than four address groups")
    values = []
    for g in groups:
        v = _parse_inet_component(g)
        if v is None:
            raise ValueError("malformed numeric group")
        values.append(v)
    *head, last = values
    # inet_aton: leading groups are single bytes; the last fills the rest.
    if any(v > 0xFF for v in head):
        raise ValueError("address group out of range")
    last_bits = 8 * (5 - len(values))
    if last > (1 << last_bits) - 1:
        raise ValueError("address out of range")
    n = 0
    for v in head:
        n = (n << 8) | v
    n = (n << last_bits) | last
    return str(ipaddress.ip_address(n))


def validate_base_url(base_url: str) -> None:
    """Reject a user-supplied external base_url that could enable SSRF (F4).

    Requires https and blocks loopback/private/link-local/reserved IP literals
    and known metadata hostnames — in **any** encoding: dotted-quad, IPv6, and
    the integer/hex/octal forms ``inet_aton`` accepts (ITM-010). (Hostnames
    that resolve to private IPs via DNS are a residual risk — see issue log.)
    """
    parsed = urlparse(base_url)
    if parsed.scheme != "https":
        raise LLMError("Custom LLM base_url must use https.")
    # NFKC-fold before any check so Unicode compatibility forms (e.g. fullwidth
    # digits U+FF11… in ``１２７.0.0.1``) collapse to their ASCII equivalents and
    # cannot slip an internal IP past the numeric detection below (review r1/R1).
    # This is the same normalization an IDNA resolver applies, so a *genuine*
    # internationalized hostname still survives as a hostname — we fold the
    # encoding, we do not reject non-ASCII outright.
    host = unicodedata.normalize("NFKC", parsed.hostname or "").lower()
    if not host or host in _BLOCKED_HOSTS:
        raise LLMError("Custom LLM base_url host is not allowed.")
    try:
        numeric = _numeric_host_to_ipv4(host)
    except ValueError:
        raise LLMError("Custom LLM base_url host is not allowed.")
    try:
        ip = ipaddress.ip_address(numeric or host)
    except ValueError:
        return  # a hostname, not an IP literal
    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
        raise LLMError("Custom LLM base_url may not point at a private/internal address.")


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
            if cfg.base_url:
                validate_base_url(cfg.base_url)  # SSRF guard on user-supplied URLs only
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
