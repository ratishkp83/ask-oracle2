from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

from tenacity import retry, stop_after_attempt, wait_exponential
from openai import OpenAI

from .schema import Schema
# Single source of truth for SQL safety (see src/core/sql_safety.py).
from .core.sql_safety import is_safe_select as sql_is_safe_select

# Groq is OpenAI-API-compatible. We just point the client at Groq's base URL
# and use a Groq model name. Set LLM_PROVIDER=openai to switch back to OpenAI.
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
DEFAULT_GROQ_MODEL = "llama3-70b-8192"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


@dataclass
class LLMConfig:
    """Per-request / per-user LLM settings.

    Any field left as ``None`` falls back to the server's environment
    configuration, so a single global default still works when no per-user
    config is supplied. The API key, when provided, is used transiently and is
    never logged or persisted by this module.
    """

    provider: Optional[str] = None  # "groq" | "openai"
    model: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None

    def is_empty(self) -> bool:
        return not any([self.provider, self.model, self.api_key, self.base_url])


def build_schema_context(schema: Schema, max_chars: int = 12000) -> str:
    text = schema.to_compact_markdown()
    if len(text) > max_chars:
        return text[: max_chars - 500] + "\n...\n(truncated schema in prompt)"
    return text


def get_llm_client() -> OpenAI:
    """OpenAI-compatible client built from environment variables.

    Priority:
      1. GROQ_API_KEY  -> Groq (api.groq.com)
      2. OPENAI_API_KEY -> OpenAI
    """
    groq_key = os.getenv("GROQ_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if groq_key:
        return OpenAI(api_key=groq_key, base_url=GROQ_BASE_URL)
    elif openai_key:
        return OpenAI(api_key=openai_key)
    else:
        raise RuntimeError(
            "No LLM API key found. Set GROQ_API_KEY (for Groq) or OPENAI_API_KEY "
            "(for OpenAI) in the environment, or supply a per-user key in Settings."
        )


def _client_from_config(config: Optional[LLMConfig]) -> OpenAI:
    """Build a client from an explicit per-user config, else fall back to env."""
    if config and config.api_key:
        provider = (config.provider or "").lower()
        base_url = config.base_url
        if not base_url and provider == "groq":
            base_url = GROQ_BASE_URL
        # For OpenAI (or unspecified) with no base_url, use the SDK default.
        if base_url:
            return OpenAI(api_key=config.api_key, base_url=base_url)
        return OpenAI(api_key=config.api_key)
    return get_llm_client()


def get_default_model() -> str:
    """Pick a sensible default model based on which provider is configured."""
    if os.getenv("GROQ_API_KEY"):
        return os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
    return os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)


def resolve_model(config: Optional[LLMConfig]) -> str:
    """Resolve the model name from per-user config, then env defaults."""
    if config and config.model:
        return config.model
    if config and config.provider:
        provider = config.provider.lower()
        if provider == "groq":
            return os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
        if provider == "openai":
            return os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
    return get_default_model()


SYSTEM_PROMPT = (
    "You are an expert Oracle SQL generator. Convert user requests into correct, efficient Oracle SQL. "
    "Rules: \n"
    "- Only return the SQL, no commentary.\n"
    "- Use only tables/columns from the provided schema.\n"
    "- Prefer explicit JOINs using relationships.\n"
    "- Use Oracle date functions (TRUNC, ADD_MONTHS, SYSDATE) where needed.\n"
    "- Avoid SELECT *. Always select named columns.\n"
    "- Generate a single query suitable for direct execution.\n"
)


@retry(wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(3))
def _call_llm(prompt: str, model: str, config: Optional[LLMConfig] = None) -> str:
    client = _client_from_config(config)

    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
    )
    sql = completion.choices[0].message.content.strip()
    # Strip code fences if present
    if sql.startswith("```"):
        sql = re.sub(r"^```[a-zA-Z]*\n|```$", "", sql, flags=re.MULTILINE).strip()
    return sql


def generate_sql_from_nl(
    natural_language: str,
    schema: Schema,
    model: Optional[str] = None,
    llm: Optional[LLMConfig] = None,
) -> str:
    """Propose Oracle SQL for a natural-language question.

    ``llm`` carries per-user provider/model/key settings; when omitted, the
    server's environment configuration is used. The result is always verified to
    be a safe SELECT/CTE before being returned.
    """
    if not natural_language or not natural_language.strip():
        raise ValueError("Empty natural language input.")
    if schema is None or not schema.tables:
        raise ValueError("Schema is empty; upload schema metadata first.")

    model_name = model or resolve_model(llm)

    schema_context = build_schema_context(schema)
    prompt = (
        "Schema:\n" + schema_context + "\n\n" +
        "User request: \n" + natural_language.strip() + "\n\n" +
        "Return only Oracle SQL."
    )

    sql = _call_llm(prompt, model=model_name, config=llm)
    if not sql_is_safe_select(sql):
        raise ValueError("Generated SQL is not a SELECT/CTE. Aborting for safety.")
    return sql
