"""Web search tool: find known fixes for an error message."""

from __future__ import annotations

import logging

import httpx
from mcp.server.mcpserver.exceptions import ToolError

from server import config
from server.redact import redact_obj

logger = logging.getLogger(__name__)


def _ddgs_search(query: str) -> list[dict]:
    from ddgs import DDGS

    last_error: Exception | None = None
    for backend in ("duckduckgo", "yandex", None):
        try:
            kwargs: dict = {"max_results": 5}
            if backend:
                kwargs["backend"] = backend
            raw = DDGS().text(query, **kwargs)
        except Exception as exc:  # ddgs raises a variety of errors per backend
            last_error = exc
            continue
        if raw:
            return [
                {
                    "title": (item.get("title") or "")[:200],
                    "url": item.get("href") or "",
                    "snippet": (item.get("body") or "")[:300],
                }
                for item in raw[:5]
            ]
    raise ToolError(
        f"Web search returned no results ({last_error}). Try again or rephrase the query."
    )


def _tavily_search(query: str) -> list[dict]:
    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT_S) as client:
            response = client.post(
                "https://api.tavily.com/search",
                json={"query": query, "max_results": 5},
                headers={"Authorization": f"Bearer {config.TAVILY_API_KEY}"},
            )
    except httpx.TimeoutException:
        raise ToolError("Tavily search timed out. Try again in a moment.") from None
    except httpx.HTTPError as exc:
        raise ToolError(f"Network error talking to Tavily: {exc}") from exc
    if response.status_code >= 400:
        raise ToolError(f"Tavily search failed ({response.status_code}). Check TAVILY_API_KEY.")
    return [
        {
            "title": (item.get("title") or "")[:200],
            "url": item.get("url") or "",
            "snippet": (item.get("content") or "")[:300],
        }
        for item in response.json().get("results", [])[:5]
    ]


def web_search_fix(error_message: str) -> dict:
    """Search the web for known fixes for an error message.

    Use after identifying the exact error signature (e.g. PaymentTimeoutError)
    to see how others have resolved it. Returns a few result titles, URLs, and
    snippets. Prefer official docs and well-known sources.
    """
    if not isinstance(error_message, str) or not error_message.strip():
        raise ToolError("error_message must be a non-empty string.")
    query = error_message.strip()[: config.MAX_SEARCH_QUERY_LEN]

    if config.WEB_SEARCH_PROVIDER == "tavily" and config.TAVILY_API_KEY:
        provider = "tavily"
        results = _tavily_search(query)
    else:
        provider = "ddgs"
        results = _ddgs_search(query)

    logger.info("web_search_fix provider=%s query=%r -> %d", provider, query, len(results))
    return redact_obj({"query": query, "provider": provider, "count": len(results), "results": results})
