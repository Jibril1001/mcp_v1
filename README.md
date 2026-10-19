# Incident Detective

**Incident Detective** is an AI on-call engineer for developers. Paste an error or
a vague complaint like "checkout is failing for some users"; it investigates by
querying an error-log database, finding related GitHub issues and recent commits,
and searching the web for known fixes, then writes and saves an evidence-backed
diagnosis.

It is built end to end on the **Model Context Protocol (MCP)**: a server exposes
the tools and data, and a user-written client connects that server to an LLM
agent loop.

---

## Architecture

```mermaid
flowchart LR
  U[User] --> A[client/agent.py<br/>host + agent loop]
  A <--> L[Google Gemini API]
  A <-->|MCP client session<br/>stdio| S[server/ MCP server]
  S --> D[(SQLite logs)]
  S --> G[GitHub REST API]
  S --> T[Web search (ddgs)]
  S --> R[reports/ folder]
```

MCP has three roles:

- **Host** — the application the user runs: `client/agent.py` (the Incident
  Detective CLI).
- **Client** — the connector inside the host. We use the SDK's `Client`, one
  session per server.
- **Server** — `server/`, which exposes tools, a resource, and (optionally) a
  prompt over stdio.

The server is independent of the LLM. The same tools work in the Inspector,
Claude Desktop, Cursor, or our own client.

---

## Prerequisites

- Python 3.10+ (developed on 3.13)
- Node.js (only for the MCP Inspector)
- An LLM key: **Groq** ([console.groq.com/keys](https://console.groq.com/keys),
  default; free tier is ~1,000 requests/day) or Google AI Studio Gemini
- Optional: a GitHub token (the public demo repo works without one, but a token
  raises the rate limit from 60 to 5000 requests/hour)
- Optional: a Tavily key (the default web search, `ddgs`, needs no key)

---

## Setup

```bash
git clone https://github.com/Jibril1001/mcp_v1.git
cd mcp_v1
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env      # Windows: Copy-Item .env.example .env
```

Fill in `.env`:

| Variable | Required | Notes |
|---|---|---|
| `LLM_PROVIDER` | no | `groq` (default) or `gemini` |
| `GROQ_API_KEY` | for groq | Groq key |
| `GROQ_MODEL` | no | default `openai/gpt-oss-120b` |
| `GROQ_BASE_URL` | no | default `https://api.groq.com/openai/v1` |
| `GEMINI_API_KEY` or `GOOGLE_API_KEY` | for gemini | Google AI Studio key |
| `GEMINI_MODEL` | no | default `gemini-2.5-flash-lite` |
| `GEMINI_BASE_URL` | no | default Gemini's OpenAI-compatible endpoint |
| `GITHUB_TOKEN` | no | fine-grained PAT (`Contents: read`, `Issues: read`); raises rate limits |
| `DEMO_REPO` | no | default `Jibril1001/test_repo` |
| `WEB_SEARCH_PROVIDER` | no | `ddgs` (default) or `tavily` |
| `TAVILY_API_KEY` | no | only for Tavily |
| `DB_PATH` | no | default `data/incidents.db` |
| `REPORTS_DIR` | no | default `reports` |
| `MCP_TOKEN_ADMIN` / `MCP_TOKEN_READONLY` | for HTTP | opaque bearer tokens; see "Run over HTTP" |
| `MCP_TOKEN` | for HTTP client | token the client sends |
| `MCP_PUBLIC_URL` | no | default `http://127.0.0.1:8000` |

Build the incident database (timestamps are relative to *now*, so run it right
before a demo):

```bash
python data/seed.py
```

### Free-tier note

The default provider is **Groq**, whose free tier allows roughly **1,000
requests/day** — plenty, since one investigation uses ~5-6 calls. If you prefer
Gemini, set `LLM_PROVIDER=gemini`; its free tier is only **20 requests/day per
model**. In both cases the client retries transient 429/5xx errors with backoff
and prints a clear message (not a traceback) when the daily quota is gone.

### Optional: the demo GitHub repo

The agent investigates `DEMO_REPO` (public). The current demo repo contains a
planted "mystery": a commit titled `Reduce payment client timeout from 30s to 3s`
and three related issues. See [`docs/PLANT.md`](docs/PLANT.md) for how it was
created and how to recreate it.

To investigate your own repo instead, set `DEMO_REPO=owner/name` in `.env`.

---

## Test the server with the MCP Inspector

List the tools:

```bash
npx @modelcontextprotocol/inspector --cli .venv/Scripts/python.exe \
  -m server.main --method tools/list
```

Call one:

```bash
npx @modelcontextprotocol/inspector --cli .venv/Scripts/python.exe \
  -m server.main --method tools/call \
  --tool-name logs_query_errors --tool-arg service=checkout
```

Open the UI:

```bash
npx @modelcontextprotocol/inspector .venv/Scripts/python.exe -m server.main
```

Captured CLI evidence is in [`docs/screenshots/`](docs/screenshots/). On
macOS/Linux use `python` instead of `.venv/Scripts/python.exe`.

---

## Run the agent

```bash
python -m client.agent "Checkout is failing for some users since this morning"
```

Add `--verbose` to see every tool call and its arguments/result. The final
diagnosis is printed and saved to `reports/`.

Example saved report: [`docs/sample_report.md`](docs/sample_report.md) (a real
run; the live files are written to `reports/`, which is gitignored).

The agent loop:

1. Connect to the server (stdio or HTTP) and call `list_tools`.
2. Convert each MCP tool to the OpenAI function format and send it to the LLM.
3. While the model returns tool calls, run them via `call_tool` and feed the
   results back (tool errors become `ERROR: ...` content).
4. Stop when the model returns a final answer. Hard cap: 10 iterations.

---

## Run over HTTP with scoped access

The server can run over Streamable HTTP instead of stdio. In HTTP mode it
requires a bearer token and enforces per-tool scopes; stdio remains trusted
local access.

Generate two tokens and put them in `.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"   # MCP_TOKEN_ADMIN
python -c "import secrets; print(secrets.token_urlsafe(32))"   # MCP_TOKEN_READONLY
```

Terminal 1 — start the server (serves `/mcp`):

```bash
python -m server.main --transport http --host 127.0.0.1 --port 8000
```

Terminal 2 — run the agent against it:

```bash
python -m client.agent "Checkout is failing for some users" \
  --transport http --url http://127.0.0.1:8000/mcp --token <ADMIN_TOKEN>
```

Scopes:

| Scope | Tools |
|---|---|
| `logs:read` | `logs_query_errors`, resource `db://schema` |
| `github:read` | `github_search_issues`, `github_list_recent_commits` |
| `web:read` | `web_search_fix` |
| `report:write` | `report_save_diagnosis` |

`MCP_TOKEN_ADMIN` gets all scopes; `MCP_TOKEN_READONLY` gets the three read
scopes and is refused on the report tool with a tool-result error
(`Token lacks scope report:write`). Requests with a missing or unknown token get
`401 invalid_token`. Tokens are compared with `hmac.compare_digest`. Verified
output is in [`docs/screenshots/http-auth.txt`](docs/screenshots/http-auth.txt).

---

## Tools

| Tool | What it does | Example call | Example result |
|---|---|---|---|
| `logs_query_errors(service, since_hours=24, limit=10, signature=None)` | Top error signatures with counts; with `signature`, an hourly timeline | `{"service": "checkout"}` | `PaymentTimeoutError` count 110, first seen at the deploy time |
| `github_search_issues(repo, query)` | Related issues | `{"repo": "Jibril1001/test_repo", "query": "PaymentTimeoutError"}` | issue #1 and #3, with URLs |
| `github_list_recent_commits(repo, since_hours=48)` | Commits shortly before a spike | `{"repo": "Jibril1001/test_repo", "since_hours": 48}` | `e2c335c Reduce payment client timeout from 30s to 3s` |
| `web_search_fix(error_message)` | Known fixes online | `{"error_message": "PaymentTimeoutError"}` | 5 results with title/url/snippet |
| `report_save_diagnosis(title, markdown)` | Save the final report | `{"title": "Checkout timeouts", "markdown": "# ..."}` | `{"saved_path": ".../reports/checkout-timeouts-....md"}` |

Also exposed:

- **Resource** `db://schema` — the `CREATE TABLE` statements for the log DB.
- **Prompt** `investigate_incident(symptom, service)` — structured investigation
  instructions (see `server/main.py`).

---

## Safety design

- **Read-only database.** The server opens SQLite with
  `file:<path>?mode=ro&uri=True`, so a tool call can never modify the logs.
- **Parameterized SQL only.** No user value is ever interpolated into SQL.
- **Input validation.** Every tool validates and bounds its arguments
  (`server/validation.py`): service allowlist, `since_hours` 1–720, `limit`
  1–100, signature regex, `owner/name` repo format.
- **Errors are results.** Tools raise `ToolError`; the model receives
  `is_error=True` with an actionable message and can retry, instead of the
  session crashing.
- **No stdout in the server.** `tests/test_no_stdout.py` fails if `print(` or
  `sys.stdout` appears under `server/` (stdout is the JSON-RPC channel).
- **Secrets and redaction.** Keys come from environment variables only. Every
  tool result passes through `server/redact.py`, which strips token-like
  strings (`ghp_…`, `github_pat_…`, `xai-…`, `tvly-…`, `AIza…`, `Bearer …`,
  long base64) while preserving 40-char commit SHAs.
- **Path traversal blocked.** Report titles are slugified and the resolved path
  must stay inside `REPORTS_DIR`; markdown is capped at 50 KB.
- **Authenticated HTTP with scoped access.** In HTTP mode every request needs a
  bearer token (constant-time compared); tools enforce scopes and return
  `Token lacks scope ...` instead of running (`server/auth.py`, `server/scopes.py`).

---

## Project structure

```
mcp_v1/
├── README.md · SUMMARY.md · PLAN.md · requirements.txt · pytest.ini
├── .env.example · .gitignore
├── data/
│   ├── seed.py            # builds data/incidents.db (deterministic)
│   └── demo_sha.txt       # culprit commit SHA used by the seed
├── server/
│   ├── main.py            # build_server(), registrations, transport flag
│   ├── config.py · validation.py · redact.py
│   ├── auth.py · scopes.py  # bearer-token verifier + per-tool scopes (HTTP)
│   └── tools/ logs.py · github.py · web.py · reports.py
├── client/
│   ├── agent.py           # CLI + agent loop (stdio or HTTP)
│   ├── mcp_bridge.py      # MCP tool defs -> OpenAI function format
│   └── llm.py             # Gemini/Groq adapter (single provider-specific file)
├── tests/ test_validation.py · test_redact.py · test_no_stdout.py · test_auth.py
├── docs/ PLANT.md · sample_report.md · screenshots/
└── reports/               # generated, gitignored
```

Run the tests:

```bash
python -m pytest -q
```

---

## Requirements checklist

| Assignment requirement | Where it is satisfied |
|---|---|
| 1–2 sentence use case | Top of this README |
| ≥2 external resources | SQLite log DB, GitHub REST API, web search |
| MCP server with tools (unique names, what/when descriptions, typed inputs, errors in result) | `server/tools/`, `server/main.py` |
| Own MCP client: connect → list → pass to LLM → run tool calls → return results | `client/agent.py`, `client/mcp_bridge.py` |
| Resource and prompt in addition to tools | `db://schema` resource + `investigate_incident` prompt (`server/main.py`) |
| Streamable HTTP (not just stdio) | `python -m server.main --transport http`; client `--transport http` |
| Authentication and scoped access | `server/auth.py`, `server/scopes.py`; see "Run over HTTP" |
| Tools integrated into the app | End-to-end demo below |
| Server tested with the Inspector | `docs/screenshots/` |
| README with setup + tool list with example calls | This file |
| Demo covering ≥2 tools | See below |
| One-page summary note | [`SUMMARY.md`](SUMMARY.md) |

**Demo scenario (≥2 tools):** `logs_query_errors` finds the
`PaymentTimeoutError` spike → its timeline shows when it started →
`github_list_recent_commits` finds the timeout-reduction commit →
`github_search_issues` finds related reports → `report_save_diagnosis` saves a
diagnosis naming commit `e2c335c`.

---

## Limitations and future work

- **HTTP auth uses static bearer tokens** from the environment. Production would
  use OAuth 2.1 with an authorization server; the SDK's OAuth hooks are the
  upgrade path.
- Web search depends on `ddgs` backends and can be flaky; Tavily is supported as
  an alternative via `WEB_SEARCH_PROVIDER=tavily`.
- The Gemini free tier is small (20 requests/day/model); Groq is the default for
  that reason.
- The seed data is synthetic. Point `DB_PATH` at a real log export to use it for
  real.
