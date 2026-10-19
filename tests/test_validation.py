import pytest

from server.validation import (
    ValidationError,
    validate_limit,
    validate_repo,
    validate_service,
    validate_signature,
    validate_since_hours,
)


def test_service_accepts_allowlisted():
    assert validate_service("checkout") == "checkout"
    assert validate_service("auth") == "auth"
    assert validate_service("search") == "search"


def test_service_rejects_unknown_with_valid_options():
    with pytest.raises(ValidationError) as exc:
        validate_service("chekout")
    message = str(exc.value)
    assert "chekout" in message
    assert "checkout" in message and "auth" in message and "search" in message


def test_since_hours_clamps_and_rejects():
    assert validate_since_hours(24) == 24
    assert validate_since_hours("6") == 6
    with pytest.raises(ValidationError):
        validate_since_hours(0)
    with pytest.raises(ValidationError):
        validate_since_hours(721)
    with pytest.raises(ValidationError):
        validate_since_hours("soon")


def test_limit_range():
    assert validate_limit(1) == 1
    assert validate_limit(100) == 100
    with pytest.raises(ValidationError):
        validate_limit(0)
    with pytest.raises(ValidationError):
        validate_limit(101)


def test_signature_optional_and_validated():
    assert validate_signature(None) is None
    assert validate_signature("PaymentTimeoutError") == "PaymentTimeoutError"
    assert validate_signature("a.b-c_1") == "a.b-c_1"
    for bad in ("has space", "semi;colon", "x" * 81, "../etc"):
        with pytest.raises(ValidationError):
            validate_signature(bad)


def test_repo_form():
    assert validate_repo("Jibril1001/test_repo") == "Jibril1001/test_repo"
    for bad in ("nope", "a/b/c", "no space/here", ""):
        with pytest.raises(ValidationError):
            validate_repo(bad)
