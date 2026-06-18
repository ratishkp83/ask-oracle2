from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Protocol, runtime_checkable


class LLMError(RuntimeError):
    """Raised for LLM provider/configuration problems (surfaced as a clean 4xx/UI message)."""


@dataclass
class LLMConfig:
    """Per-request / per-user LLM settings. Any field left ``None`` falls back to
    the server environment. The api_key is used transiently — never logged or
    persisted by this package.
    """

    provider: Optional[str] = None  # "groq" | "openai"
    model: Optional[str] = None
    # repr=False so a stray log/traceback never prints the secret (F6).
    api_key: Optional[str] = field(default=None, repr=False)
    base_url: Optional[str] = None

    def is_empty(self) -> bool:
        return not any([self.provider, self.model, self.api_key, self.base_url])


@dataclass
class Confidence:
    level: str  # "High" | "Medium" | "Low"
    reasons: List[str] = field(default_factory=list)


@dataclass
class NLSQLResult:
    sql: str
    explanation: Optional[str] = None
    confidence: Optional[Confidence] = None
    # Off-topic guard (conservative): False when the request isn't answerable from
    # the provided schema (not a data question). Then `sql` is empty and `message`
    # carries a short, user-facing reason; the UI proposes/runs nothing.
    answerable: bool = True
    message: Optional[str] = None
    # The user's request restated as the model understood it (typo-corrected,
    # disambiguated) so results correlate to intent. Shown as "Showing results
    # for: …" — never row data, just a faithful paraphrase of the question.
    interpreted_question: Optional[str] = None


@runtime_checkable
class LLMProvider(Protocol):
    """Minimal interface every provider implements."""

    name: str

    def is_available(self) -> bool:
        """True if the provider is configured and can serve requests."""
        ...

    def resolve_model(self, requested: Optional[str] = None) -> str:
        ...

    def complete(self, system: str, user: str, model: Optional[str] = None) -> str:
        ...
