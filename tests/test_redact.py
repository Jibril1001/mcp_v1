from server.redact import redact, redact_obj


def test_redacts_known_token_prefixes():
    samples = [
        "github_pat_11ABCDEFG0123456789_abcdefghijklmnop",
        "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
        "xai-abcdefghijklmnopqrstuvwxyz0123456789",
        "tvly-dev-abcDEF1234567890",
        "sk-abcdefghijklmnopqrstuvwxyz0123",
        "AIzaSyA1234567890abcdefghijklmnopqrstu",
        "Authorization: Bearer abcdef1234567890",
    ]
    for sample in samples:
        assert "[REDACTED]" in redact(sample), sample
        assert "abcdef" not in redact(sample).lower().replace("[redacted]", ""), sample


def test_preserves_commit_sha():
    sha = "1ab1f68b39dd5051d9024453e96fdef2733b7192"
    assert redact(f"culprit commit {sha}") == f"culprit commit {sha}"


def test_redact_obj_recurses():
    payload = {
        "results": [
            {"note": "token=ghp_abcdefghijklmnopqrstuvwxyz0123456789", "sha": "a" * 40}
        ]
    }
    cleaned = redact_obj(payload)
    assert "ghp_" not in str(cleaned)
    assert cleaned["results"][0]["sha"] == "a" * 40


def test_empty_values_pass_through():
    assert redact("") == ""
    assert redact_obj(None) is None
