"""LLM adapter: Google Gemini through its OpenAI-compatible endpoint.

All provider-specific code lives here so swapping providers is a few lines
(change the base URL / model / key and everything else keeps working).
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

_API_KEY = (
    os.environ.get("GEMINI_API_KEY")
    or os.environ.get("GOOGLE_API_KEY")
    or ""
).strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite").strip()
GEMINI_BASE_URL = os.environ.get(
    "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
).strip()
GEMINI_MAX_TOKENS = int(os.environ.get("GEMINI_MAX_TOKENS", "8192"))
# Gemini 2.5 Flash spends part of max_tokens on internal "thinking"; "low"
# keeps responses short and reliable while still allowing tool use.
GEMINI_REASONING_EFFORT = os.environ.get("GEMINI_REASONING_EFFORT", "low").strip()
DEMO_REPO = os.environ.get("DEMO_REPO", "Jibril1001/test_repo").strip()


def make_client() -> OpenAI:
    if not _API_KEY:
        raise SystemExit(
            "No Gemini API key found. Set GEMINI_API_KEY (or GOOGLE_API_KEY) in .env."
        )
    return OpenAI(
        api_key=_API_KEY,
        base_url=GEMINI_BASE_URL,
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
                "model": model or GEMINI_MODEL,
                "messages": messages,
                "max_tokens": GEMINI_MAX_TOKENS,
            }
            if tools:
                kwargs["tools"] = tools
            if GEMINI_REASONING_EFFORT:
                kwargs["reasoning_effort"] = GEMINI_REASONING_EFFORT
            return client.chat.completions.create(**kwargs)
        except Exception as exc:  # noqa: BLE001 - normalize provider errors
            last_error = exc
            if _is_daily_quota(exc):
                raise QuotaExceeded(
                    "The Gemini API daily quota is exhausted for "
                    f"{model or GEMINI_MODEL}. Wait for the daily reset, enable "
                    "billing on the Google Cloud project, or set GEMINI_MODEL to "
                    "another model in .env."
                ) from exc
            if _is_retryable(exc) and attempt < 5:
                time.sleep(min(2 ** attempt, 20))
                continue
            raise
    raise last_error
