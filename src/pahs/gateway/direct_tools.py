"""Direct external tool execution — deliver results without review interrupts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pahs.external.registry import get_external_agent, strip_external_prefix
from pahs.external.runner import run_external_agent
from pahs.gateway.run_ids import new_run_id
from pahs.gateway.telegram_session import set_smas_review
from pahs.storage import db

SMAS_REVIEW_FOOTER = (
    "\n\n——\n"
    "满意回复：好\n"
    "要修改回复：改：你的修改意见"
)


def _format_smas_delivery(result: dict[str, Any]) -> tuple[str, str | None]:
    preview = result.get("preview_image") or (result.get("parsed_json") or {}).get("preview_image")
    image_path = str(preview) if preview and Path(str(preview)).exists() else None
    body = str(result.get("text") or "预览已生成，请看上图。").strip()
    if image_path:
        body = body + SMAS_REVIEW_FOOTER
    return body, image_path


def _format_pip_delivery(result: dict[str, Any]) -> tuple[str, str | None]:
    body = str(result.get("text") or "PIP finished.")
    job_id = result.get("job_id")
    if job_id:
        body = f"Job ID: {job_id}\n\n{body}"
    return body, None


def execute_direct_tool(
    agent_name: str,
    command: str,
    *,
    channel: str = "telegram",
    channel_user_id: str | None = None,
) -> dict[str, Any]:
    spec = get_external_agent(agent_name)
    if spec is None:
        raise ValueError(f"External tool `{agent_name}` is not enabled.")

    prompt = strip_external_prefix(command, spec) or command.strip()
    run_id = new_run_id()
    db.create_run(run_id, prompt, channel=channel, status="ACTIVE")

    try:
        result = run_external_agent(agent_name, prompt, run_id=run_id)
    except Exception as exc:
        db.update_run(run_id, status="FAILED")
        raise

    if agent_name == "smas":
        delivery_text, image_path = _format_smas_delivery(result)
    elif agent_name == "pip":
        delivery_text, image_path = _format_pip_delivery(result)
    else:
        delivery_text = str(result.get("text") or "")
        image_path = None

    status = "COMPLETED" if result.get("ok") else "FAILED"
    if agent_name == "smas" and image_path and channel == "telegram" and channel_user_id:
        status = "AWAITING_REVIEW"
        set_smas_review(channel_user_id, run_id=run_id, image_path=image_path)

    db.update_run(run_id, status=status)
    db.log_event(
        run_id,
        "direct_tool_delivery",
        {
            "agent_name": agent_name,
            "ok": result.get("ok"),
            "image_path": image_path,
        },
    )

    return {
        "action": "deliver",
        "run_id": run_id,
        "agent_name": agent_name,
        "ok": bool(result.get("ok")),
        "text": delivery_text,
        "image_path": image_path,
        "awaiting_review": status == "AWAITING_REVIEW",
        "raw": result,
    }


def execute_smas_review(
    chat_id: str,
    review_text: str,
    *,
    channel: str = "telegram",
) -> dict[str, Any]:
    from pahs.external.smas_bridge import run_smas_action
    from pahs.gateway.telegram_session import clear_session, get_session, parse_smas_review_reply
    from pahs.external.registry import get_external_agent

    session = get_session(chat_id)
    if not session or session.get("tool") != "smas":
        raise ValueError("No SMAS preview waiting for review.")

    action, payload = parse_smas_review_reply(review_text)
    if action == "approve":
        smas_text = "ok"
    else:
        smas_text = f"edit: {payload}"

    spec = get_external_agent("smas")
    if spec is None:
        raise ValueError("SMAS is not enabled.")

    run_id = str(session.get("run_id"))
    result = run_smas_action(spec, smas_text)
    clear_session(chat_id)
    db.update_run(run_id, status="COMPLETED")
    db.log_event(run_id, "smas_review_reply", {"action": action, "text": review_text})

    preview = result.get("preview_image") or (result.get("parsed_json") or {}).get("preview_image")
    image_path = str(preview) if preview and Path(str(preview)).exists() else None

    if action == "approve":
        text = "已保存草稿，这版定稿了。"
    elif image_path:
        caption = str(result.get("text") or "").strip()
        text = "已按你的意见改好了，请看新预览：" + (f"\n\n{caption}" if caption else "")
    else:
        text = str(result.get("text") or "已按你的意见修改。")

    return {
        "action": "deliver",
        "run_id": run_id,
        "agent_name": "smas",
        "ok": bool(result.get("ok")),
        "text": text,
        "image_path": image_path,
        "awaiting_review": False,
        "raw": result,
    }
