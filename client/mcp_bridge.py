"""Translate MCP tool definitions into the OpenAI function-calling format."""

from __future__ import annotations

from typing import Any, Iterable


def mcp_tool_to_openai(tool: Any) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema
            or {"type": "object", "properties": {}, "additionalProperties": False},
        },
    }


def mcp_tools_to_openai(tools: Iterable[Any]) -> list[dict]:
    return [mcp_tool_to_openai(tool) for tool in tools]
