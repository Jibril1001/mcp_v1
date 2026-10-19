"""LLM adapter: Google Gemini or Groq through OpenAI-compatible endpoints.

All provider-specific code lives here so swapping providers is a few env vars:

    LLM_PROVIDER=groq    -> GROQ_API_KEY, GROQ_MODEL, GROQ_BASE_URL
    LLM_PROVIDER=gemini  -> GEMINI_API_KEY (or GOOGLE_API_KEY), GEMINI_MODEL

The default is Groq because its free tier allows ~1,000 requests/day, versus
Gemini's 20 requests/day per model.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)

PROVIDER = os.environ.get("LLM_PROVIDER", "groq").strip().lower()

_GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite").strip()
_GEMINI_BASE_URL = os.environ.get(
    "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
).strip()
_GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-120b").strip()
_GROQ_BASE_URL = os.environ.get(
    "GROQ_BASE_URL", "https://api.groq.com/openai/v1"
).strip()

if PROVIDER == "groq":
    API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
    BASE_URL = _GROQ_BASE_URL
    ACTIVE_MODEL = _GROQ_MODEL
    # Groq's free tier caps tokens per minute; keep the completion budget small.
    MAX_TOKENS = int(os.environ.get("GROQ_MAX_TOKENS", "2048"))
    REASONING_EFFORT = os.environ.get("GROQ_REASONING_EFFORT", "").strip()
    KEY_ENV = "GROQ_API_KEY"
elif PROVIDER == "gemini":
    API_KEY = (
        os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
    ).strip()
    BASE_URL = _GEMINI_BASE_URL
    ACTIVE_MODEL = _GEMINI_MODEL
    MAX_TOKENS = int(os.environ.get("GEMINI_MAX_TOKENS", "8192"))
    # Gemini 2.5 Flash spends part of max_tokens on internal "thinking".
    REASONING_EFFORT = os.environ.get("GEMINI_REASONING_EFFORT", "low").strip()
    KEY_ENV = "GEMINI_API_KEY (or GOOGLE_API_KEY)"
else:
    raise ValueError(f"Unknown LLM_PROVIDER {PROVIDER!r}; use 'groq' or 'gemini'.")

DEMO_REPO = os.environ.get("DEMO_REPO", "Jibril1001/test_repo").strip()

# Kept for callers that still refer to the Gemini-specific names.
GEMINI_MODEL = _GEMINI_MODEL
GEMINI_BASE_URL = _GEMINI_BASE_URL


def make_client() -> OpenAI:
    if not API_KEY:
        raise SystemExit(f"No {PROVIDER} API key found. Set {KEY_ENV} in .env.")
    return OpenAI(
        api_key=API_KEY,
        base_url=BASE_URL,
        timeout=httpx.Timeout(120.0, connect=15.0),
        max_retries=0,
    )


_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_RETRYABLE_TEXT = ("rate", "429", "unavailable", "high demand", "overloaded", "try again")
_DAILY_QUOTA_TEXT = (
    "resource_exhausted",
    "exceeded your current quota",
    "free_tier_requests",
    "generaterequestsperday",
    "per day (rpd)",
    "tokens per day (tpd)",
)


class QuotaExceeded(RuntimeError):
    """The provider's daily quota is exhausted (retrying will not help)."""


def _is_retryable(exc: Exception) -> bool:
    status = getattr(exc, "status_code", None)
    if status in _RETRYABLE_STATUS:
        return True
    text = str(exc).lower()
    return any(marker in text for marker in _RETRYABLE_TEXT)


def _is_daily_quota(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in _DAILY_QUOTA_TEXT)


def complete(client: OpenAI, messages: list[dict], tools: list[dict] | None, model: str | None = None):
    """One chat completion with backoff on transient provider errors (429/5xx)."""
    last_error: Exception | None = None
    for attempt in range(6):
        try:
            kwargs: dict = {
                "model": model or ACTIVE_MODEL,
                "messages": messages,
                "max_tokens": MAX_TOKENS,
            }
            if tools:
                kwargs["tools"] = tools
            if REASONING_EFFORT:
                kwargs["reasoning_effort"] = REASONING_EFFORT
            return client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 - normalize provider errors
            last_error = exc
            if _is_daily_quota(exc):
                raise QuotaExceeded(
                    f"The {PROVIDER} API daily quota is exhausted for "
                    f"{model or ACTIVE_MODEL}. Wait for the daily reset, enable "
                    "billing, or set LLM_PROVIDER / the model in .env."
                ) from exc
            if _is_retryable(exc) and attempt < 5:
                time.sleep(min(2 ** attempt, 20))
                continue
            raise
    raise last_error
