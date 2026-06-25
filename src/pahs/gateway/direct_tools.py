"""Direct external tool execution — deliver results without review interrupts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pahs.external.registry import get_external_agent, strip_external_prefix
from pahs.external.runner import run_external_agent
from pahs.gateway.run_ids import new_run_id
from pahs.storage import db


def _format_smas_delivery(result: dict[str, Any]) -> tuple[str, str | None]:
    parsed = result.get("parsed_json") or {}
    lines: list[str] = []
    text = parsed.get("text")
    if text:
        lines.append(str(text).strip())
    critic = parsed.get("critic")
    if isinstance(critic, dict) and critic.get("summary"):
        lines.append(f"Critic: {critic['summary']}")
    preview = parsed.get("preview_image")
    image_path = str(preview) if preview and Path(str(preview)).exists() else None
    if image_path:
        lines.append(f"Preview image: {image_path}")
    body = "\n\n".join(line for line in lines if line).strip()
    if not body:
        body = str(result.get("text") or "SMAS finished with no text output.")
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
        "raw": result,
    }
