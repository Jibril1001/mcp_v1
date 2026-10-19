"""Bearer-token authentication for the Streamable HTTP transport.

Two opaque tokens come from the environment:

- MCP_TOKEN_ADMIN    -> logs:read, github:read, web:read, report:write
- MCP_TOKEN_READONLY -> logs:read, github:read, web:read

Tokens are compared with `hmac.compare_digest` so verification is constant-time.
Production would use OAuth 2.1 instead of static tokens; this is enough for the
assignment and local demos.
"""

from __future__ import annotations

import hmac

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings

from server import config
from server.scopes import ADMIN_SCOPES, READONLY_SCOPES


class EnvTokenVerifier:
    """Resolve a bearer token to an AccessToken with its scopes."""

    def __init__(self, tokens: dict[str, tuple[str, list[str]]] | None = None) -> None:
        if tokens is None:
            tokens = {
                config.MCP_TOKEN_ADMIN: ("admin", ADMIN_SCOPES),
                config.MCP_TOKEN_READONLY: ("readonly", READONLY_SCOPES),
            }
        self._tokens = {raw: info for raw, info in tokens.items() if raw}

    async def verify_token(self, token: str) -> AccessToken | None:
        for expected, (client_id, scopes) in self._tokens.items():
            if hmac.compare_digest(token, expected):
                return AccessToken(
                    token=token,
                    client_id=client_id,
                    scopes=list(scopes),
                )
        return None


def build_auth() -> tuple[TokenVerifier | None, AuthSettings | None]:
    """Return the verifier and settings, or (None, None) when disabled."""
    if not (config.MCP_TOKEN_ADMIN and config.MCP_TOKEN_READONLY):
        return None, None
    verifier = EnvTokenVerifier()
    settings = AuthSettings(
        issuer_url=config.MCP_PUBLIC_URL,
        resource_server_url=f"{config.MCP_PUBLIC_URL}/mcp",
        required_scopes=None,
        # Tokens are opaque and not audience-scoped, so the verifier decides.
        validate_token_resource=False,
    )
    return verifier, settings
