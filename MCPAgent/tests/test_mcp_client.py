import unittest

import httpx

from chat_service import _parse_arguments, answer_question
from mcp_client import MCPError, parse_mcp_response


class FakeMCPClient:
    def __init__(self):
        self.initialized = False
        self.calls = []

    def initialize(self):
        self.initialized = True

    def list_tools(self):
        return [
            {
                "name": "microsoft_docs_search",
                "description": "Search Microsoft Learn.",
                "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
            }
        ]

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return {"content": [{"type": "text", "text": "Official result"}]}


class FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, exclude_none=True):
        result = {"role": "assistant"}
        if self.content is not None:
            result["content"] = self.content
        if self.tool_calls is not None:
            result["tool_calls"] = self.tool_calls
        return result


class FakeToolCall:
    id = "call-1"

    class function:
        name = "microsoft_docs_search"
        arguments = '{"query":"Azure Functions authentication"}'


class FakeModelClient:
    def __init__(self):
        self.responses = iter(
            [
                FakeMessage(tool_calls=[FakeToolCall()]),
                FakeMessage(content="Use the official result: https://learn.microsoft.com/example"),
            ]
        )
        self.chat = self
        self.completions = self

    def create(self, **kwargs):
        return type("Response", (), {"choices": [type("Choice", (), {"message": next(self.responses)})()]})()


class MCPClientTests(unittest.TestCase):
    def test_parse_json_rpc_response(self):
        response = httpx.Response(
            200, json={"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}
        )

        self.assertTrue(parse_mcp_response(response)["result"]["ok"])

    def test_parse_sse_json_rpc_response(self):
        response = httpx.Response(
            200,
            headers={"content-type": "text/event-stream"},
            text='event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}\n\n',
        )

        self.assertTrue(parse_mcp_response(response)["result"]["ok"])

    def test_parse_mcp_error(self):
        response = httpx.Response(200, json={"error": {"message": "bad request"}})

        with self.assertRaisesRegex(MCPError, "bad request"):
            parse_mcp_response(response)

    def test_answer_question_executes_model_tool_call(self):
        mcp_client = FakeMCPClient()

        answer = answer_question(FakeModelClient(), mcp_client, [{"role": "user", "content": "Find auth docs"}], "test-model")

        self.assertIn("https://learn.microsoft.com/example", answer)
        self.assertTrue(mcp_client.initialized)
        self.assertEqual(
            mcp_client.calls,
            [("microsoft_docs_search", {"query": "Azure Functions authentication"})],
        )

    def test_parse_arguments_requires_object(self):
        with self.assertRaises(ValueError):
            _parse_arguments('["not", "an", "object"]')
