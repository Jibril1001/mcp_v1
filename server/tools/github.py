"""GitHub tools: related issues and recent commits via the REST API."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import httpx
from mcp.server.mcpserver.exceptions import ToolError

from server import config
from server.redact import redact_obj
from server.validation import (
    ValidationError,
    validate_repo,
    validate_since_hours,
)

logger = logging.getLogger(__name__)


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if config.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {config.GITHUB_TOKEN}"
    return headers


def _raise_for_status(response: httpx.Response) -> None:
    status = response.status_code
    if status == 404:
        raise ToolError(
            f"Repository not found (404). Check the owner/name (e.g. {config.DEMO_REPO})."
        )
    if status == 401:
        raise ToolError("GitHub authentication failed (401). Check GITHUB_TOKEN in .env.")
    if status == 403:
        if response.headers.get("x-ratelimit-remaining") == "0":
            raise ToolError(
                "GitHub rate limit exceeded. Set GITHUB_TOKEN in .env for a higher limit."
            )
        raise ToolError("GitHub refused the request (403). Check token permissions and rate limits.")
    if status >= 400:
        raise ToolError(f"GitHub request failed ({status}).")


def _get(url: str, params: dict) -> list | dict:
    try:
        with httpx.Client(timeout=config.HTTP_TIMEOUT_S) as client:
            response = client.get(url, params=params, headers=_headers())
    except httpx.TimeoutException:
        raise ToolError("GitHub request timed out. Try again in a moment.") from None
    except httpx.HTTPError as exc:
        raise ToolError(f"Network error talking to GitHub: {exc}") from exc
    _raise_for_status(response)
    return response.json()


def github_search_issues(repo: str, query: str) -> dict:
    """Find GitHub issues related to a symptom or error.

    Use to check whether the problem is already reported, or to gather context
    on a service. `repo` is 'owner/name'; `query` is free text, e.g. the error
    signature or a short symptom description.
    """
    try:
        repo = validate_repo(repo)
    except ValidationError as exc:
        raise ToolError(str(exc)) from exc
    if not isinstance(query, str) or not query.strip():
        raise ToolError("query must be a non-empty search string.")

    data = _get(
        f"{config.GITHUB_API}/search/issues",
        {"q": f"repo:{repo} is:issue {query.strip()}", "per_page": config.MAX_ITEMS},
    )
    items = [
        {
            "number": item["number"],
            "title": item["title"],
            "state": item["state"],
            "url": item["html_url"],
            "created_at": item["created_at"],
        }
        for item in data.get("items", [])[: config.MAX_ITEMS]
    ]
    logger.info("github_search_issues repo=%s query=%r -> %d", repo, query, len(items))
    return redact_obj({"repo": repo, "query": query, "count": len(items), "issues": items})


def github_list_recent_commits(repo: str, since_hours: int = 48) -> dict:
    """List recent commits to a repository.

    Use after you know roughly when an error started, to see what code changed
    just before. `repo` is 'owner/name'; `since_hours` bounds the window.
    """
    try:
        repo = validate_repo(repo)
        since_hours = validate_since_hours(since_hours)
    except ValidationError as exc:
        raise ToolError(str(exc)) from exc

    since = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    data = _get(
        f"{config.GITHUB_API}/repos/{repo}/commits",
        {"since": since, "per_page": config.MAX_ITEMS},
    )
    commits = [
        {
            "sha": commit["sha"][:7],
            "full_sha": commit["sha"],
            "message": commit["commit"]["message"].splitlines()[0],
            "author": (commit.get("author") or {}).get("login")
            or commit["commit"]["author"]["name"],
            "date": commit["commit"]["author"]["date"],
        }
        for commit in data[: config.MAX_ITEMS]
    ]
    logger.info("github_list_recent_commits repo=%s since_hours=%s -> %d", repo, since_hours, len(commits))
    return redact_obj({"repo": repo, "since_hours": since_hours, "count": len(commits), "commits": commits})
