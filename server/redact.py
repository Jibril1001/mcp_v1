"""Strip token-like strings from tool output before it reaches the model."""

from __future__ import annotations

import re
from typing import Any

_PATTERNS = (
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"gho_[A-Za-z0-9]{20,}"),
    re.compile(r"xai-[A-Za-z0-9]{20,}"),
    re.compile(r"tvly-[A-Za-z0-9_-]{10,}"),
    re.compile(r"sk-[A-Za-z0-9-]{20,}"),
    re.compile(r"AIza[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{8,}"),
    re.compile(r"[A-Za-z0-9+/]{60,}={0,2}"),
)

_REPLACEMENT = "[REDACTED]"


def redact(text: str) -> str:
    """Replace token-like substrings in *text* with ``[REDACTED]``."""
    if not text:
        return text
    for pattern in _PATTERNS:
        text = pattern.sub(_REPLACEMENT, text)
    return text


def redact_obj(obj: Any) -> Any:
    """Recursively redact strings in a JSON-like structure."""
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {key: redact_obj(value) for key, value in obj.items()}
    if isinstance(obj, list):
        return [redact_obj(item) for item in obj]
    return obj
