"""Unified gateway for CLI, Telegram, and future channels."""

from __future__ import annotations

import re
from typing import Any

from pahs.external.registry import match_external_agent
from pahs.gateway.run_ids import new_run_id
from pahs.graph.runner import resume_run, start_run
from pahs.storage import db

RUN_ID_PATTERN = re.compile(r"run_\d{8}_\d{6}_[a-f0-9]{4}")


def parse_reply_command(text: str) -> tuple[str, str] | None:
    stripped = text.strip()
    if not stripped.lower().startswith("reply "):
        return None
    parts = stripped.split(maxsplit=2)
    if len(parts) < 3:
        return None
    _, run_id, message = parts
    return run_id, message


def parse_run_command(text: str) -> str | None:
    stripped = text.strip()
    if stripped.lower().startswith("run "):
        return stripped[4:].strip()
    if match_external_agent(stripped):
        return stripped
    return None


def _interrupt_message(result: dict[str, Any]) -> str | None:
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None
    item = interrupts[0]
    value = getattr(item, "value", item)
    if not isinstance(value, dict):
        return None
    if value.get("type") == "milestone_review":
        return str(value.get("presentation") or "")
    if value.get("type") == "final_feedback":
        return str(value.get("final_response") or "")
    return None


def format_pending_lines() -> list[str]:
    rows = db.list_pending_reviews()
    if not rows:
        return ["No pending reviews.", "没有待审核任务。"]
    lines = []
    for row in rows:
        lines.append(
            f"- run_id={row['run_id']} type={row['review_type']} command={row['command']}"
        )
    return lines


def handle_inbound_text(
    text: str,
    *,
    channel: str,
    channel_user_id: str,
    user_id: str = "default",
) -> dict[str, Any]:
    db.init_db()
    db.resolve_user_id(channel, channel_user_id, default=user_id)

    reply = parse_reply_command(text)
    if reply is not None:
        run_id, message = reply
        result = resume_run(run_id, message, channel=channel)
        return {"action": "reply", "run_id": run_id, "result": result}

    if text.strip().lower() == "pending":
        return {"action": "pending", "lines": format_pending_lines()}

    run_match = RUN_ID_PATTERN.search(text)
    if run_match and text.strip().lower().startswith("status "):
        run_id = run_match.group(0)
        row = db.get_run(run_id)
        return {"action": "status", "run_id": run_id, "run": row}

    command = parse_run_command(text)
    if command:
        run_id = new_run_id()
        result = start_run(run_id, command, channel=channel)
        return {
            "action": "run",
            "run_id": run_id,
            "command": command,
            "result": result,
            "interrupt_message": _interrupt_message(result),
        }

    return {
        "action": "help",
        "message": (
            "PAHS main agent ready.\n\n"
            "Start a task:\n"
            "run <command>\n"
            "@smas <IG post task>\n"
            "@pip <video task>\n\n"
            "Review:\n"
            "reply <run_id> approved\n"
            "pending"
        ),
    }
