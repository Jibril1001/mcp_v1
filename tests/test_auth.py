import asyncio

import pytest
from mcp.server.auth.middleware.auth_context import auth_context_var
from mcp.server.auth.middleware.bearer_auth import AuthenticatedUser
from mcp.server.auth.provider import AccessToken
from mcp.server.mcpserver.exceptions import ToolError

from server.auth import ADMIN_SCOPES, READONLY_SCOPES, EnvTokenVerifier
from server.scopes import require_scope


def _verifier() -> EnvTokenVerifier:
    return EnvTokenVerifier(
        {
            "admin-secret": ("admin", ADMIN_SCOPES),
            "read-secret": ("readonly", READONLY_SCOPES),
        }
    )


def test_verifier_returns_admin_scopes():
    token = asyncio.run(_verifier().verify_token("admin-secret"))
    assert token is not None
    assert token.client_id == "admin"
    assert "report:write" in token.scopes


def test_verifier_readonly_has_no_write_scope():
    token = asyncio.run(_verifier().verify_token("read-secret"))
    assert token is not None
    assert set(token.scopes) == set(READONLY_SCOPES)
    assert "report:write" not in token.scopes


def test_verifier_rejects_unknown_and_empty():
    verifier = _verifier()
    assert asyncio.run(verifier.verify_token("nope")) is None
    assert asyncio.run(verifier.verify_token("")) is None


def test_verifier_ignores_blank_tokens():
    verifier = EnvTokenVerifier({"": ("admin", ADMIN_SCOPES), "x": ("admin", ADMIN_SCOPES)})
    assert asyncio.run(verifier.verify_token("")) is None
    assert asyncio.run(verifier.verify_token("x")) is not None


def _activate(scopes: list[str]):
    user = AuthenticatedUser(AccessToken(token="t", client_id="c", scopes=list(scopes)))
    return auth_context_var.set(user)


def test_require_scope_allows_without_token():
    require_scope("report:write")  # stdio/local mode is trusted


def test_require_scope_blocks_readonly_write():
    reset = _activate(READONLY_SCOPES)
    try:
        require_scope("logs:read")
        with pytest.raises(ToolError, match="report:write"):
            require_scope("report:write")
    finally:
        auth_context_var.reset(reset)


def test_require_scope_allows_admin_write():
    reset = _activate(ADMIN_SCOPES)
    try:
        require_scope("report:write")
    finally:
        auth_context_var.reset(reset)
