"""Scope names and per-tool permission checks.

The Streamable HTTP transport authenticates a bearer token and stores its scopes
in a context variable. Tools call `require_scope` to enforce access. When there
is no token (stdio/local mode) access is trusted, because the process is started
by the same user.
"""

from __future__ import annotations

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.mcpserver.exceptions import ToolError

LOGS_READ = "logs:read"
GITHUB_READ = "github:read"
WEB_READ = "web:read"
REPORT_WRITE = "report:write"

READONLY_SCOPES = [LOGS_READ, GITHUB_READ, WEB_READ]
ADMIN_SCOPES = [*READONLY_SCOPES, REPORT_WRITE]


def require_scope(scope: str) -> None:
    """Raise a tool-result permission error if the caller lacks `scope`."""
    token = get_access_token()
    if token is None:
        return  # stdio/local mode: trusted
    if scope not in token.scopes:
        raise ToolError(f"Token lacks scope {scope}")
