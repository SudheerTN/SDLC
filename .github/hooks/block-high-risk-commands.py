"""Deny high-risk terminal commands before an agent executes them."""

import json
import re
import sys
from typing import Any

TERMINAL_TOOLS = {
    "execute",
    "run_in_terminal",
    "terminal",
}
MCP_TOOL_PREFIXES = ("mcp__", "mcp_", "mcp.", "mcp:")
ALLOWED_MCP_NAMESPACES = {
    "github",
    "microsoftdocs",
    "local-documents",
}

HIGH_RISK_PATTERNS = (
    (r"\bgit\s+(?:reset\s+--hard|clean\s+-[^\s]*f|checkout\s+--\s+\.|restore\s+\.)\b", "destructive Git operation"),
    (r"\bgit\s+push\b[^\n]*\s(?:-f|--force)(?:\s|$)", "force push"),
    (r"\brm\s+(?:-[^\s]*r[^\s]*f|-[^\s]*f[^\s]*r)\b", "recursive forced deletion"),
    (r"\bremove-item\b[^\n]*\-(?:recurse|force)\b", "forced PowerShell deletion"),
    (r"\brmdir\s+/s\b|\bdel\s+/f\b", "forced Windows deletion"),
    (r"\b(?:mkfs|diskpart|format\.com)\b", "disk formatting operation"),
    (r"\bdd\s+if=", "raw disk write"),
    (r"\b(?:shutdown|restart-computer|stop-computer)\b", "system power operation"),
)


def command_from_input(tool_input: Any) -> str:
    if isinstance(tool_input, str):
        return tool_input
    if not isinstance(tool_input, dict):
        return ""
    for key in ("command", "cmd", "commands", "script"):
        value = tool_input.get(key)
        if isinstance(value, str):
            return value
    return ""


def mcp_namespace(tool_name: str) -> str | None:
    for prefix in MCP_TOOL_PREFIXES:
        if tool_name.startswith(prefix):
            remainder = tool_name[len(prefix) :]
            return re.split(r"__|[_\.:/]", remainder, maxsplit=1)[0]
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError):
        return 0

    tool_name = str(payload.get("toolName", payload.get("tool_name", ""))).lower()
    namespace = mcp_namespace(tool_name)
    if namespace is not None and namespace not in ALLOWED_MCP_NAMESPACES:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": f"MCP namespace '{namespace}' is not allowed by workspace policy.",
                    }
                }
            )
        )
        return 2

    if tool_name not in TERMINAL_TOOLS:
        return 0

    command = command_from_input(payload.get("toolInput", payload.get("tool_input")))
    normalized = re.sub(r"\s+", " ", command.strip().lower())
    for pattern, reason in HIGH_RISK_PATTERNS:
        if re.search(pattern, normalized, re.IGNORECASE):
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": f"Blocked {reason}. Run it manually after reviewing the impact.",
                        }
                    }
                )
            )
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
