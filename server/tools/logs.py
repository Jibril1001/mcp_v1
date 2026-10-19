"""Error-log tools: query the incident SQLite database (read-only)."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta, timezone

from mcp.server.mcpserver.exceptions import ToolError

from server import config, scopes
from server.redact import redact_obj
from server.scopes import require_scope
from server.validation import (
    ValidationError,
    validate_limit,
    validate_service,
    validate_signature,
    validate_since_hours,
)

logger = logging.getLogger(__name__)

_SCHEMA_QUERY = (
    "SELECT sql FROM sqlite_master "
    "WHERE type IN ('table', 'index') AND sql IS NOT NULL ORDER BY name"
)


def _connect() -> sqlite3.Connection:
    """Open the incidents DB read-only so a tool call can never mutate it."""
    uri = f"file:{config.DB_PATH}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def db_schema_text() -> str:
    """Return the CREATE TABLE / CREATE INDEX statements as text."""
    require_scope(scopes.LOGS_READ)
    try:
        conn = _connect()
    except sqlite3.Error as exc:
        raise ToolError(
            f"Could not open the incident database at {config.DB_PATH}: {exc}. "
            "Run 'python data/seed.py' to create it."
        ) from exc
    try:
        rows = conn.execute(_SCHEMA_QUERY).fetchall()
        return "\n\n".join(row[0] for row in rows) + "\n"
    finally:
        conn.close()


def logs_query_errors(
    service: str,
    since_hours: int = 24,
    limit: int = 10,
    signature: str | None = None,
) -> dict:
    """Query the application error-log database.

    Use this FIRST to find which errors are spiking for a service. Without
    `signature`, returns the top error signatures with counts and first/last
    seen. With `signature`, returns an hourly timeline of that one error so you
    can see exactly when it started.
    """
    require_scope(scopes.LOGS_READ)
    try:
        service = validate_service(service)
        since_hours = validate_since_hours(since_hours)
        limit = validate_limit(limit)
        signature = validate_signature(signature)
    except ValidationError as exc:
        raise ToolError(str(exc)) from exc

    since = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat()

    try:
        conn = _connect()
    except sqlite3.Error as exc:
        raise ToolError(
            f"Could not open the incident database at {config.DB_PATH}: {exc}. "
            "Run 'python data/seed.py' to create it."
        ) from exc

    try:
        if signature:
            rows = conn.execute(
                "SELECT substr(ts, 1, 13) AS hour, COUNT(*) AS count "
                "FROM error_logs WHERE service = ? AND signature = ? AND ts >= ? "
                "GROUP BY hour ORDER BY hour",
                (service, signature, since),
            ).fetchall()
            result = {
                "service": service,
                "signature": signature,
                "since_hours": since_hours,
                "timeline": [{"hour": hour, "count": count} for hour, count in rows],
            }
        else:
            rows = conn.execute(
                "SELECT signature, COUNT(*) AS count, MIN(ts), MAX(ts) "
                "FROM error_logs WHERE service = ? AND ts >= ? "
                "GROUP BY signature ORDER BY count DESC LIMIT ?",
                (service, since, limit),
            ).fetchall()
            result = {
                "service": service,
                "since_hours": since_hours,
                "signatures": [
                    {
                        "signature": sig,
                        "count": count,
                        "first_seen": first,
                        "last_seen": last,
                    }
                    for sig, count, first, last in rows
                ],
            }
    except sqlite3.Error as exc:
        raise ToolError(f"Query failed: {exc}") from exc
    finally:
        conn.close()

    logger.info(
        "logs_query_errors service=%s since_hours=%s signature=%s -> %d rows",
        service,
        since_hours,
        signature,
        len(result.get("timeline") or result.get("signatures") or []),
    )
    return redact_obj(result)
