"""Incident Detective CLI: an MCP client + agent loop.

Connects to the MCP server over stdio, lists its tools, hands them to the LLM,
runs the tool calls the model asks for, and feeds the results back until the
model produces a final answer.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import anyio
from mcp import Client, StdioServerParameters
from mcp.types import TextContent

from client import llm
from client.mcp_bridge import mcp_tools_to_openai

ROOT = Path(__file__).resolve().parent.parent
MAX_ITERATIONS = 10

SYSTEM_PROMPT = (
    "You are Incident Detective, an on-call engineer. Investigate AUTONOMOUSLY "
    "using the provided tools and NEVER ask the user questions or for "
    "clarification; make reasonable assumptions and proceed.\n"
    "Pick the service from the symptom: 'checkout' for payment/checkout/order "
    "problems, 'auth' for login/token problems, 'search' for search problems. "
    "If unsure, use 'checkout'.\n"
    "Work in this order: (1) logs_query_errors(service) to find the top error "
    "signature; (2) logs_query_errors(service, signature=<that>) to get the "
    "hourly timeline and when it started; (3) github_list_recent_commits for the "
    "repo, using a window that starts before the error's first-seen time (if it "
    "returns none, retry with a larger since_hours, up to 720); (4) "
    "github_search_issues for related reports; (5) web_search_fix only if useful.\n"
    "Base every claim on tool output and name the tool that produced it. If a "
    "tool returns an error, read it and retry with corrected arguments. Do not "
    "stop until you have saved the diagnosis. Call report_save_diagnosis with a "
    "report containing: summary, timeline, suspected cause (with the commit SHA), "
    "evidence, and recommended fix. Never invent data."
)

# Only these OS-critical variables are needed for the subprocess to run; the
# server gets everything else explicitly from the SERVER_ENV_KEYS below.
_PASSTHROUGH = (
    "PATH", "SystemRoot", "SystemDrive", "windir", "TEMP", "TMP", "PATHEXT",
    "COMSPEC", "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "OS",
    "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "APPDATA", "LOCALAPPDATA",
    "PROGRAMDATA", "PYTHONIOENCODING",
)
SERVER_ENV_KEYS = (
    "DB_PATH", "REPORTS_DIR", "GITHUB_TOKEN", "TAVILY_API_KEY",
    "WEB_SEARCH_PROVIDER", "DEMO_REPO",
)


def _server_env() -> dict[str, str]:
    env = {key: os.environ[key] for key in _PASSTHROUGH if os.environ.get(key)}
    env.update({key: os.environ[key] for key in SERVER_ENV_KEYS if os.environ.get(key)})
    env.setdefault("PYTHONUTF8", "1")
    return env


def _content_to_text(result) -> str:
    parts = [block.text for block in result.content if isinstance(block, TextContent)]
    text = "\n".join(parts).strip()
    if not text and getattr(result, "structured_content", None) is not None:
        text = json.dumps(result.structured_content, ensure_ascii=False)
    return text or "(no content)"


def _log(verbose: bool, message: str) -> None:
    if verbose:
        print(message, file=sys.stderr, flush=True)


async def run_agent(user_input: str, model: str | None, verbose: bool) -> int:
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "server.main"],
        env=_server_env(),
        cwd=str(ROOT),
    )
    llm_client = llm.make_client()

    async with Client(params) as client:
        tools_result = await client.list_tools()
        tools = mcp_tools_to_openai(tools_result.tools)
        _log(verbose, f"Discovered {len(tools)} MCP tools: " + ", ".join(t.name for t in tools_result.tools))

        messages: list[dict] = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
                + f"\n\nThe code lives in GitHub repo {llm.DEMO_REPO}.",
            },
            {"role": "user", "content": user_input},
        ]

        empty_retries = 0
        for step in range(1, MAX_ITERATIONS + 1):
            _log(verbose, f"[step {step}] asking {llm.GEMINI_MODEL}...")
            response = llm.complete(llm_client, messages, tools, model=model)
            message = response.choices[0].message
            tool_calls = message.tool_calls or []

            if not tool_calls:
                content = (message.content or "").strip()
                if content:
                    print(content)
                    return 0
                empty_retries += 1
                if empty_retries > 2:
                    print("The model returned an empty answer. Please try again.")
                    return 1
                _log(verbose, "  (empty response; nudging the model)")
                messages.append(
                    {
                        "role": "user",
                        "content": "Continue: either call a tool, or give your final diagnosis now.",
                    }
                )
                continue

            messages.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": call.function.name,
                                "arguments": call.function.arguments,
                            },
                        }
                        for call in tool_calls
                    ],
                }
            )

            for call in tool_calls:
                name = call.function.name
                try:
                    arguments = json.loads(call.function.arguments or "{}")
                except json.JSONDecodeError as exc:
                    _log(verbose, f"  ! {name}: invalid JSON arguments")
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": f"ERROR: invalid JSON in arguments: {exc}",
                        }
                    )
                    continue

                _log(verbose, f"  -> {name}({json.dumps(arguments, ensure_ascii=False)})")
                try:
                    result = await client.call_tool(name, arguments)
                    text = _content_to_text(result)
                    if result.is_error:
                        text = "ERROR: " + text
                except Exception as exc:  # noqa: BLE001 - never crash the loop on a tool call
                    text = f"ERROR: tool call failed: {exc}"
                _log(verbose, f"  <- {text.splitlines()[0][:160]}")

                messages.append({"role": "tool", "tool_call_id": call.id, "content": text})

        print(
            f"Reached the maximum of {MAX_ITERATIONS} steps without a final answer. "
            "Here is what was gathered last:",
            file=sys.stderr,
        )
        return 1


async def _main_async(argv: list[str] | None) -> int:
    parser = argparse.ArgumentParser(
        prog="client.agent",
        description="Ask Incident Detective to investigate a production problem.",
    )
    parser.add_argument("symptom", help="e.g. \"Checkout is failing for some users\"")
    parser.add_argument("--model", default=None, help="Override GEMINI_MODEL")
    parser.add_argument("--verbose", action="store_true", help="Show the tool-call trace")
    args = parser.parse_args(argv)
    return await run_agent(args.symptom, args.model, args.verbose)


def _flatten_error(exc: BaseException) -> str:
    parts = [str(exc)]
    for sub in getattr(exc, "exceptions", ()) or ():
        parts.append(_flatten_error(sub))
    return " | ".join(part for part in parts if part)


def main(argv: list[str] | None = None) -> int:
    try:
        return anyio.run(_main_async, argv)
    except SystemExit:
        raise
    except Exception as exc:  # includes ExceptionGroup from the MCP task group
        print(f"Agent stopped: {_flatten_error(exc)}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
