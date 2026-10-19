"""Incident Detective MCP server.

Registers the tools/resources/prompts and exposes them over stdio (default) or
Streamable HTTP. HTTP mode additionally requires a bearer token and enforces
per-tool scopes.
"""

from __future__ import annotations

import argparse
import logging
import sys

from mcp.server import MCPServer

from server.auth import build_auth
from server.tools import github, logs, reports, web

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("incident_detective")

INSTRUCTIONS = (
    "Tools for investigating production incidents: query an error-log database, "
    "search GitHub issues and recent commits, search the web for known fixes, and "
    "save a diagnosis report."
)


def build_server(enable_auth: bool) -> MCPServer:
    auth_kwargs: dict = {}
    if enable_auth:
        verifier, settings = build_auth()
        if verifier is None or settings is None:
            raise SystemExit(
                "HTTP mode requires MCP_TOKEN_ADMIN and MCP_TOKEN_READONLY. "
                "Generate two long random strings and set them in .env."
            )
        auth_kwargs = {"token_verifier": verifier, "auth": settings}

    server = MCPServer("Incident Detective", instructions=INSTRUCTIONS, **auth_kwargs)

    server.add_tool(logs.logs_query_errors)
    server.add_tool(github.github_search_issues)
    server.add_tool(github.github_list_recent_commits)
    server.add_tool(web.web_search_fix)
    server.add_tool(reports.report_save_diagnosis)

    @server.resource("db://schema")
    def db_schema() -> str:
        """The CREATE TABLE statements for the incident error-log database."""
        return logs.db_schema_text()

    @server.prompt()
    def investigate_incident(symptom: str, service: str = "checkout") -> str:
        """Structured investigation steps for an incident symptom."""
        return (
            f"Investigate this production symptom: {symptom}\n\n"
            f"1. Call logs_query_errors(service='{service}') to rank the top error "
            "signatures.\n"
            "2. Call logs_query_errors again with the top signature to get its hourly "
            "timeline and first-seen time.\n"
            "3. Call github_list_recent_commits with a window that starts before that "
            "time; if it returns none, widen since_hours (up to 720).\n"
            "4. Call github_search_issues for the signature.\n"
            "5. Save the diagnosis with report_save_diagnosis: summary, timeline, "
            "suspected cause (with commit SHA), evidence, and recommended fix."
        )

    return server


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Incident Detective MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "streamable-http"],
        default="stdio",
        help="stdio (default) or Streamable HTTP (requires bearer tokens)",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    transport = "streamable-http" if args.transport == "http" else args.transport
    server = build_server(enable_auth=transport != "stdio")
    logger.info("starting Incident Detective on transport=%s", transport)
    if transport == "stdio":
        server.run(transport="stdio")
    else:
        server.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            streamable_http_path="/mcp",
        )


if __name__ == "__main__":
    main()
