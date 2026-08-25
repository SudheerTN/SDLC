"""Append a redacted, bounded audit record for each completed tool action."""

import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_PREVIEW_LENGTH = 500
SECRET_PATTERN = re.compile(
    r"(?i)(authorization|api[_-]?key|password|passwd|secret|token|private[_-]?key)"
    r"\s*[:=]\s*([^\s,;]+)"
)


def first_value(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def safe_preview(value: Any) -> str | None:
    if value is None:
        return None
    try:
        text = value if isinstance(value, str) else json.dumps(value, default=str)
    except (TypeError, ValueError):
        text = str(value)
    text = SECRET_PATTERN.sub(r"\1=[REDACTED]", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:MAX_PREVIEW_LENGTH] + ("..." if len(text) > MAX_PREVIEW_LENGTH else "")


def output_summary(value: Any) -> dict[str, Any]:
    preview = safe_preview(value)
    return {
        "type": type(value).__name__ if value is not None else None,
        "length": len(value) if isinstance(value, (str, list, dict)) else None,
        "preview": preview,
    }


def write_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as audit_log:
        audit_log.write(json.dumps(record, ensure_ascii=True) + "\n")


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError):
        return 0

    if not isinstance(payload, dict):
        return 0

    output = first_value(payload, "toolResponse", "tool_response", "toolOutput", "tool_output")
    error = first_value(payload, "error", "toolError", "tool_error")
    decision = first_value(payload, "decision", "permissionDecision", "permission_decision")
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "PostToolUse",
        "tool": first_value(payload, "toolName", "tool_name"),
        "status": "error" if error else "completed",
        "decision": safe_preview(decision),
        "input": output_summary(first_value(payload, "toolInput", "tool_input")),
        "output": output_summary(output),
        "error": safe_preview(error),
    }

    configured_path = os.environ.get("COPILOT_HOOK_AUDIT_LOG")
    log_path = (
        Path(configured_path)
        if configured_path
        else Path(tempfile.gettempdir()) / "customagent-tool-audit.jsonl"
    )
    try:
        write_record(log_path, record)
        if error:
            configured_alert_path = os.environ.get("COPILOT_HOOK_ALERT_LOG")
            alert_path = (
                Path(configured_alert_path)
                if configured_alert_path
                else Path(tempfile.gettempdir()) / "customagent-tool-alerts.jsonl"
            )
            write_record(
                alert_path,
                {
                    "timestamp": record["timestamp"],
                    "event": "ToolErrorEscalation",
                    "tool": record["tool"],
                    "error": record["error"],
                    "audit_log": str(log_path),
                },
            )
    except OSError:
        # Auditing must not make an otherwise successful tool action fail.
        return 0

    if error:
        print(
            json.dumps(
                {
                    "continue": True,
                    "systemMessage": "Tool failure captured and escalated to the local alert log.",
                }
            )
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
