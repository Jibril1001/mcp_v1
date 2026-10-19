"""Incident Detective MCP server.

Registers the tools/resources/prompts and exposes them over stdio (default) or
Streamable HTTP. Runs identically on both transports.
"""

from __future__ import annotations

import argparse
import logging
import sys

from mcp.server import MCPServer

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

mcp = MCPServer("Incident Detective", instructions=INSTRUCTIONS)

mcp.add_tool(logs.logs_query_errors)
mcp.add_tool(github.github_search_issues)
mcp.add_tool(github.github_list_recent_commits)
mcp.add_tool(web.web_search_fix)
mcp.add_tool(reports.report_save_diagnosis)


@mcp.resource("db://schema")
def db_schema() -> str:
    """The CREATE TABLE statements for the incident error-log database."""
    return logs.db_schema_text()


@mcp.prompt()
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


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Incident Detective MCP server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "streamable-http"],
        default="stdio",
        help="stdio (default) or Streamable HTTP",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    transport = "streamable-http" if args.transport == "http" else args.transport
    logger.info("starting Incident Detective on transport=%s", transport)
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
