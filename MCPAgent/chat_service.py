"""LLM orchestration for grounded Microsoft Learn answers."""

from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from mcp_client import MicrosoftLearnMCP

SYSTEM_PROMPT = """You are a Microsoft Learn documentation assistant.

Use the Microsoft Learn MCP tools before answering questions about Microsoft,
Azure, .NET, Windows, PowerShell, Microsoft 365, or developer technologies.
Use only information supported by retrieved Microsoft sources. Include clickable
Microsoft Learn URLs for factual claims. Mention versions, platforms, and
prerequisites when documented. If the sources do not support an answer, say so.
Never invent APIs, parameters, limits, or product behavior.
"""


def _tool_result_text(result: dict[str, Any]) -> str:
    content = result.get("content", [])
    parts = [item.get("text", "") for item in content if item.get("type") == "text"]
    return "\n".join(parts) or str(result)


def _parse_arguments(arguments: str) -> dict[str, Any]:
    parsed = json.loads(arguments or "{}")
    if not isinstance(parsed, dict):
        raise ValueError("MCP tool arguments must be a JSON object.")
    return parsed


def answer_question(
    model_client: OpenAI,
    mcp_client: MicrosoftLearnMCP,
    conversation: list[dict[str, str]],
    model_name: str,
    max_tool_rounds: int = 8,
) -> str:
    """Answer one question by allowing the model to call Microsoft Learn tools."""
    mcp_client.initialize()
    tools = mcp_client.list_tools()
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(conversation)

    openai_tools = [
        {
            "type": "function",
            "function": {
                "name": tool["name"],
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", {"type": "object", "properties": {}}),
            },
        }
        for tool in tools
    ]

    for _ in range(max_tool_rounds):
        response = model_client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=openai_tools or None,
            tool_choice="auto" if openai_tools else None,
        )
        message = response.choices[0].message
        messages.append(message.model_dump(exclude_none=True))
        if not message.tool_calls:
            return message.content or "I could not find a supported answer in Microsoft Learn."

        for tool_call in message.tool_calls:
            tool = next((item for item in tools if item["name"] == tool_call.function.name), None)
            if tool is None:
                tool_output = f"Unknown MCP tool: {tool_call.function.name}"
            else:
                tool_output = _tool_result_text(
                    mcp_client.call_tool(
                        tool_call.function.name,
                        _parse_arguments(tool_call.function.arguments),
                    )
                )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_output,
                }
            )

    raise RuntimeError("The model exceeded the Microsoft Learn tool-call limit.")
