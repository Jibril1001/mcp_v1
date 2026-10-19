"""Report tool: save the final diagnosis to the reports/ folder."""

from __future__ import annotations

import logging
import re
import time

from mcp.server.mcpserver.exceptions import ToolError

from server import config, scopes
from server.redact import redact
from server.scopes import require_scope

logger = logging.getLogger(__name__)

_NON_SLUG = re.compile(r"[^a-z0-9]+")
_MAX_SLUG_LEN = 60


def _slugify(title: str) -> str:
    slug = _NON_SLUG.sub("-", title.lower()).strip("-")
    return slug[:_MAX_SLUG_LEN] or "diagnosis"


def report_save_diagnosis(title: str, markdown: str) -> dict:
    """Save the final diagnosis report as a Markdown file.

    Use once you have a confident diagnosis with evidence. `title` is a short
    summary; `markdown` is the full report (summary, timeline, suspected cause
    with commit SHA, evidence, recommended fix). Returns the saved file path.
    """
    require_scope(scopes.REPORT_WRITE)
    if not isinstance(title, str) or not title.strip():
        raise ToolError("title must be a non-empty string.")
    if len(title) > config.MAX_TITLE_LEN:
        raise ToolError(f"title is too long (max {config.MAX_TITLE_LEN} characters).")
    if not isinstance(markdown, str) or not markdown.strip():
        raise ToolError("markdown must be a non-empty string.")

    encoded = markdown.encode("utf-8")
    if len(encoded) > config.MAX_MARKDOWN_BYTES:
        raise ToolError(
            f"markdown is too large ({len(encoded)} bytes); max {config.MAX_MARKDOWN_BYTES}."
        )

    reports_dir = config.REPORTS_DIR.resolve()
    reports_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{_slugify(title)}-{time.strftime('%Y%m%d-%H%M%S')}.md"
    target = (reports_dir / filename).resolve()
    if target.parent != reports_dir:
        raise ToolError("Invalid report path.")

    target.write_text(redact(markdown), encoding="utf-8")
    logger.info("report_save_diagnosis wrote %s (%d bytes)", target, len(encoded))
    return {"saved_path": str(target), "bytes": len(encoded), "title": title}
