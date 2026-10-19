"""Pure validation helpers (no I/O).

Every function raises :class:`ValidationError` with an actionable message that is
safe to hand back to the model, naming the valid options where relevant.
"""

from __future__ import annotations

import re

from server import config

SIGNATURE_RE = re.compile(r"^[A-Za-z0-9_.-]{1,%d}$" % config.MAX_SIGNATURE_LEN)
REPO_RE = re.compile(r"^[\w.-]+/[\w.-]+$")


class ValidationError(ValueError):
    """Invalid tool argument. Message is safe to show the model."""


def validate_service(service: str) -> str:
    if not isinstance(service, str) or service not in config.ALLOWED_SERVICES:
        valid = ", ".join(config.ALLOWED_SERVICES)
        raise ValidationError(
            f"Unknown service {service!r}. Valid services: {valid}."
        )
    return service


def validate_since_hours(value: object) -> int:
    try:
        hours = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValidationError(
            f"since_hours must be an integer between {config.MIN_SINCE_HOURS} "
            f"and {config.MAX_SINCE_HOURS}."
        ) from None
    if not config.MIN_SINCE_HOURS <= hours <= config.MAX_SINCE_HOURS:
        raise ValidationError(
            f"since_hours must be between {config.MIN_SINCE_HOURS} and "
            f"{config.MAX_SINCE_HOURS}, got {hours}."
        )
    return hours


def validate_limit(value: object) -> int:
    try:
        limit = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise ValidationError(
            f"limit must be an integer between {config.MIN_LIMIT} and {config.MAX_LIMIT}."
        ) from None
    if not config.MIN_LIMIT <= limit <= config.MAX_LIMIT:
        raise ValidationError(
            f"limit must be between {config.MIN_LIMIT} and {config.MAX_LIMIT}, got {limit}."
        )
    return limit


def validate_signature(signature: str | None) -> str | None:
    if signature is None:
        return None
    if not isinstance(signature, str) or not SIGNATURE_RE.match(signature):
        raise ValidationError(
            "signature must match ^[A-Za-z0-9_.-]{1,%d}$ (e.g. PaymentTimeoutError)."
            % config.MAX_SIGNATURE_LEN
        )
    return signature


def validate_repo(repo: str) -> str:
    if not isinstance(repo, str) or not REPO_RE.match(repo):
        raise ValidationError(
            f"repo must be in 'owner/name' form (e.g. {config.DEMO_REPO}), got {repo!r}."
        )
    return repo
