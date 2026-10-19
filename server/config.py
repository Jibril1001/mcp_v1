"""Configuration and constants for the Incident Detective MCP server."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)


def _path(env_name: str, default: Path) -> Path:
    raw = os.environ.get(env_name)
    if not raw:
        return default
    candidate = Path(raw)
    return candidate if candidate.is_absolute() else (ROOT / candidate)


DB_PATH = _path("DB_PATH", ROOT / "data" / "incidents.db")
REPORTS_DIR = _path("REPORTS_DIR", ROOT / "reports")

DEMO_REPO = os.environ.get("DEMO_REPO", "Jibril1001/test_repo")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
TAVILY_API_KEY = os.environ.get("TAVILY_API_KEY", "").strip()
WEB_SEARCH_PROVIDER = os.environ.get("WEB_SEARCH_PROVIDER", "ddgs").strip().lower()

# Streamable HTTP auth. Tokens are opaque strings; leave blank to disable.
MCP_TOKEN_ADMIN = os.environ.get("MCP_TOKEN_ADMIN", "").strip()
MCP_TOKEN_READONLY = os.environ.get("MCP_TOKEN_READONLY", "").strip()
MCP_PUBLIC_URL = os.environ.get("MCP_PUBLIC_URL", "http://127.0.0.1:8000").strip().rstrip("/")

ALLOWED_SERVICES = ("checkout", "auth", "search")

MIN_SINCE_HOURS = 1
MAX_SINCE_HOURS = 720
MIN_LIMIT = 1
MAX_LIMIT = 100
MAX_SIGNATURE_LEN = 80

GITHUB_API = "https://api.github.com"
HTTP_TIMEOUT_S = 10.0
MAX_ITEMS = 10

MAX_MARKDOWN_BYTES = 50_000
MAX_TITLE_LEN = 120
MAX_SEARCH_QUERY_LEN = 300
