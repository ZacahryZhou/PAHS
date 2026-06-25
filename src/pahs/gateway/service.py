"""Unified gateway for CLI, Telegram, and future channels."""

from __future__ import annotations

import re
from typing import Any

from pahs.config_loader import gateway_config
from pahs.external.registry import match_external_agent
from pahs.gateway.direct_tools import execute_direct_tool
from pahs.gateway.intent_router import infer_external_agent
from pahs.gateway.persona import (
    PAHS_PERSONA_SYSTEM,
    friendly_help,
    normalize_telegram_input,
    quick_reply,
    strip_robotic_prefix,
)
from pahs.gateway.run_ids import new_run_id
from pahs.graph.runner import resume_run, start_run
from pahs.storage import db

RUN_ID_PATTERN = re.compile(r"run_\d{8}_\d{6}_[a-f0-9]{4}")


def _telegram_direct_tools() -> bool:
    return bool(gateway_config().get("gateway", {}).get("telegram_direct_tools", True))


def _telegram_chat_fallback() -> bool:
    return bool(gateway_config().get("gateway", {}).get("telegram_chat_fallback", True))


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


def _handle_telegram_chat(text: str) -> dict[str, Any]:
    if text == "__help__":
        return {"action": "chat", "text": friendly_help()}

    fast = quick_reply(text)
    if fast:
        return {"action": "chat", "text": fast}

    from pahs.providers.router import llm_complete

    answer = llm_complete(
        system=PAHS_PERSONA_SYSTEM,
        user=text,
        phase="telegram_chat",
    )
    return {"action": "chat", "text": strip_robotic_prefix(answer)}


def handle_inbound_text(
    text: str,
    *,
    channel: str,
    channel_user_id: str,
    user_id: str = "default",
    normalized: bool = False,
) -> dict[str, Any]:
    db.init_db()
    db.resolve_user_id(channel, channel_user_id, default=user_id)
    stripped = text.strip()
    if channel == "telegram" and not normalized:
        stripped = normalize_telegram_input(stripped)

    reply = parse_reply_command(text)
    if reply is not None:
        run_id, message = reply
        result = resume_run(run_id, message, channel=channel)
        return {"action": "reply", "run_id": run_id, "result": result}

    if stripped.lower() == "pending":
        return {"action": "pending", "lines": format_pending_lines()}

    run_match = RUN_ID_PATTERN.search(text)
    if run_match and stripped.lower().startswith("status "):
        run_id = run_match.group(0)
        row = db.get_run(run_id)
        return {"action": "status", "run_id": run_id, "run": row}

    # Telegram direct mode: natural language -> SMAS / PIP -> immediate delivery.
    if channel == "telegram" and _telegram_direct_tools():
        from pahs.gateway.telegram_session import get_session, is_smas_review_reply
        from pahs.gateway.direct_tools import execute_smas_review

        if is_smas_review_reply(stripped) and get_session(channel_user_id):
            return execute_smas_review(channel_user_id, stripped, channel=channel)

        tool = infer_external_agent(stripped)
        if tool is not None:
            return execute_direct_tool(
                tool.name,
                stripped,
                channel=channel,
                channel_user_id=channel_user_id,
            )

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

    if channel == "telegram" and _telegram_chat_fallback() and stripped:
        return _handle_telegram_chat(stripped)

    return {"action": "chat", "text": friendly_help()}
