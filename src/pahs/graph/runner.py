"""Run orchestration helpers for CLI and future channels."""

from __future__ import annotations

from typing import Any

from langgraph.types import Command

from pahs.graph.main import build_graph, graph_config
from pahs.storage import db


def _extract_interrupts(result: dict[str, Any]) -> list[Any]:
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return []
    return list(interrupts)


def _sync_review_queue(run_id: str, interrupt_value: dict[str, Any]) -> None:
    review_type = interrupt_value.get("type", "unknown")
    milestone_id = interrupt_value.get("milestone_id")
    db.enqueue_review(run_id, review_type, interrupt_value, milestone_id=milestone_id)

    if review_type == "milestone_review":
        db.update_run(
            run_id,
            status="AWAITING_REVIEW",
            current_milestone_id=milestone_id,
        )
    elif review_type == "final_feedback":
        db.update_run(run_id, status="AWAITING_FINAL_FEEDBACK")


def start_run(run_id: str, command: str, *, channel: str = "cli") -> dict[str, Any]:
    graph = build_graph()
    config = graph_config(run_id)

    initial_state = {
        "run_id": run_id,
        "user_command": command,
        "channel": channel,
    }

    db.create_run(run_id, command, channel=channel, status="ACTIVE")
    result = graph.invoke(initial_state, config=config)

    for item in _extract_interrupts(result):
        value = getattr(item, "value", item)
        if isinstance(value, dict):
            _sync_review_queue(run_id, value)

    return result


def resume_run(run_id: str, user_input: str, *, channel: str = "cli") -> dict[str, Any]:
    graph = build_graph()
    config = graph_config(run_id)

    pending = db.list_pending_reviews()
    pending_for_run = [row for row in pending if row["run_id"] == run_id]
    if not pending_for_run:
        raise ValueError(f"No pending review for run_id={run_id}")

    review_type = pending_for_run[-1]["review_type"]
    resolved = db.resolve_pending_review(run_id, review_type, channel=channel)
    if resolved is None:
        raise ValueError(f"Could not resolve pending review for run_id={run_id}")

    result = graph.invoke(Command(resume=user_input), config=config)

    interrupts = _extract_interrupts(result)
    for item in interrupts:
        value = getattr(item, "value", item)
        if isinstance(value, dict):
            _sync_review_queue(run_id, value)

    if not interrupts and result.get("status") == "COMPLETED":
        db.update_run(run_id, status="COMPLETED")

    return result
