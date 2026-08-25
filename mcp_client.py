"""Minimal synchronous MCP client for Microsoft Learn's HTTP server."""

from __future__ import annotations

import json
from typing import Any

import httpx


class MCPError(RuntimeError):
    """Raised when the MCP server returns a protocol or transport error."""


def parse_mcp_response(response: httpx.Response) -> dict[str, Any]:
    """Parse JSON and Server-Sent Events responses returned by MCP servers."""
    if response.status_code >= 400:
        raise MCPError(f"Microsoft Learn MCP returned HTTP {response.status_code}.")

    content_type = response.headers.get("content-type", "")
    if "text/event-stream" not in content_type:
        payload = response.json()
    else:
        payload = None
        for line in response.text.splitlines():
            if line.startswith("data:"):
                data = line[5:].strip()
                if data and data != "[DONE]":
                    payload = json.loads(data)
        if payload is None:
            raise MCPError("Microsoft Learn MCP returned no JSON-RPC response.")

    if "error" in payload:
        error = payload["error"]
        raise MCPError(error.get("message", "Microsoft Learn MCP returned an error."))
    return payload


class MicrosoftLearnMCP:
    """Synchronous Streamable HTTP MCP client with one session per chat request."""

    def __init__(self, url: str, timeout: float = 45.0, client: httpx.Client | None = None):
        self.url = url
        self._client = client or httpx.Client(timeout=timeout)
        self._owns_client = client is None
        self._request_id = 0
        self.session_id: str | None = None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "MicrosoftLearnMCP":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._request_id += 1
        body = {"jsonrpc": "2.0", "id": self._request_id, "method": method}
        if params is not None:
            body["params"] = params
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        response = self._client.post(self.url, headers=headers, json=body)
        session_id = response.headers.get("Mcp-Session-Id")
        if session_id:
            self.session_id = session_id
        return parse_mcp_response(response)

    def _notify(self, method: str) -> None:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        response = self._client.post(
            self.url,
            headers=headers,
            json={"jsonrpc": "2.0", "method": method},
        )
        if response.status_code >= 400:
            raise MCPError(f"Microsoft Learn MCP returned HTTP {response.status_code}.")

    def initialize(self) -> None:
        self._request(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "microsoft-learn-web-chat", "version": "1.0.0"},
            },
        )
        self._notify("notifications/initialized")

    def list_tools(self) -> list[dict[str, Any]]:
        return self._request("tools/list").get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self._request("tools/call", {"name": name, "arguments": arguments}).get(
            "result", {}
        )
