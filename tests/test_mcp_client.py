import httpx
import unittest

from mcp_client import MCPError, parse_mcp_response


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
