"""Background run execution for Dev Lab."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from typing import Any

from pahs.gateway.run_ids import new_run_id
from pahs.graph.runner import resume_run, start_run
from pahs.storage import db


@dataclass
class RunHandle:
    run_id: str
    command: str
    status: str = "STARTING"
    error: str | None = None
    last_result: dict[str, Any] = field(default_factory=dict)
    interrupt_message: str | None = None
    review_type: str | None = None


_lock = threading.Lock()
_active: dict[str, RunHandle] = {}


def _extract_interrupt(result: dict[str, Any]) -> tuple[str | None, str | None]:
    interrupts = result.get("__interrupt__")
    if not interrupts:
        return None, None
    item = interrupts[0]
    value = getattr(item, "value", item)
    if not isinstance(value, dict):
        return None, None
    review_type = str(value.get("type") or "unknown")
    if review_type == "milestone_review":
        return review_type, str(value.get("presentation") or "")
    if review_type == "final_feedback":
        return review_type, str(value.get("final_response") or "")
    return review_type, json.dumps(value, ensure_ascii=False)


def _sync_handle_from_db(handle: RunHandle) -> None:
    row = db.get_run(handle.run_id)
    if row:
        handle.status = str(row.get("status") or handle.status)


def extract_run_error(run_id: str, handle: RunHandle | None = None) -> str | None:
    if handle and handle.error:
        return handle.error
    for event in reversed(db.list_run_events(run_id)):
        et = str(event.get("event_type", ""))
        payload = event.get("payload") or {}
        if et == "devlab_run_failed":
            return str(payload.get("error") or "Run failed")
        if et == "validation_failed":
            return str(payload.get("message") or "Validation failed")
    return None


def _finalize_failed(handle: RunHandle) -> None:
    handle.error = extract_run_error(handle.run_id, handle)


def start_run_async(command: str) -> RunHandle:
    db.init_db()
    run_id = new_run_id()
    handle = RunHandle(run_id=run_id, command=command)
    with _lock:
        _active[run_id] = handle

    db.log_event(run_id, "devlab_run_started", {"command": command, "channel": "devlab"})

    def worker() -> None:
        try:
            handle.status = "ACTIVE"
            result = start_run(run_id, command, channel="devlab")
            handle.last_result = result
            review_type, message = _extract_interrupt(result)
            if review_type:
                handle.review_type = review_type
                handle.interrupt_message = message
                handle.status = "AWAITING_REVIEW" if review_type == "milestone_review" else "AWAITING_FINAL_FEEDBACK"
                db.log_event(
                    run_id,
                    "devlab_interrupt",
                    {"review_type": review_type, "preview": (message or "")[:500]},
                )
            elif result.get("status") == "COMPLETED":
                handle.status = "COMPLETED"
                db.log_event(run_id, "devlab_run_completed", {"status": "COMPLETED"})
            else:
                _sync_handle_from_db(handle)
                if handle.status == "FAILED":
                    _finalize_failed(handle)
        except Exception as exc:
            handle.status = "FAILED"
            handle.error = str(exc)
            db.log_event(run_id, "devlab_run_failed", {"error": str(exc), "node_id": "orchestrator_plan"})
            db.update_run(run_id, status="FAILED")

    thread = threading.Thread(target=worker, name=f"devlab-{run_id}", daemon=True)
    thread.start()
    return handle


def resume_run_async(run_id: str, message: str) -> RunHandle:
    with _lock:
        handle = _active.get(run_id) or RunHandle(run_id=run_id, command="")
        _active[run_id] = handle

    def worker() -> None:
        try:
            handle.status = "ACTIVE"
            handle.interrupt_message = None
            handle.review_type = None
            result = resume_run(run_id, message, channel="devlab")
            handle.last_result = result
            review_type, interrupt_message = _extract_interrupt(result)
            if review_type:
                handle.review_type = review_type
                handle.interrupt_message = interrupt_message
                handle.status = (
                    "AWAITING_REVIEW"
                    if review_type == "milestone_review"
                    else "AWAITING_FINAL_FEEDBACK"
                )
                db.log_event(
                    run_id,
                    "devlab_interrupt",
                    {"review_type": review_type, "preview": (interrupt_message or "")[:500]},
                )
            elif result.get("status") == "COMPLETED":
                handle.status = "COMPLETED"
                db.log_event(run_id, "devlab_run_completed", {"status": "COMPLETED"})
            else:
                _sync_handle_from_db(handle)
                if handle.status == "FAILED":
                    _finalize_failed(handle)
        except Exception as exc:
            handle.status = "FAILED"
            handle.error = str(exc)
            db.log_event(run_id, "devlab_run_failed", {"error": str(exc), "node_id": "verify_pipeline"})

    thread = threading.Thread(target=worker, name=f"devlab-resume-{run_id}", daemon=True)
    thread.start()
    return handle


def get_handle(run_id: str) -> RunHandle | None:
    with _lock:
        handle = _active.get(run_id)
    if handle:
        _sync_handle_from_db(handle)
        return handle
    row = db.get_run(run_id)
    if row is None:
        return None
    return RunHandle(
        run_id=run_id,
        command=str(row.get("command") or ""),
        status=str(row.get("status") or "UNKNOWN"),
    )


def run_snapshot(run_id: str) -> dict[str, Any]:
    handle = get_handle(run_id)
    row = db.get_run(run_id)
    if row is None:
        return {"error": "not_found"}

    plan = {}
    if row.get("plan_json"):
        try:
            plan = json.loads(row["plan_json"])
        except json.JSONDecodeError:
            plan = {}

    pending = [r for r in db.list_pending_reviews() if r["run_id"] == run_id]
    waiting_review = bool(pending) or (handle and handle.status in {"AWAITING_REVIEW", "AWAITING_FINAL_FEEDBACK"})

    error = extract_run_error(run_id, handle)

    return {
        "run_id": run_id,
        "command": row.get("command"),
        "status": handle.status if handle else row.get("status"),
        "error": error,
        "waiting_review": waiting_review,
        "review_type": handle.review_type if handle else (pending[-1]["review_type"] if pending else None),
        "interrupt_message": handle.interrupt_message if handle else None,
        "execution_plan": plan.get("execution_plan"),
        "plan_source": plan.get("plan_source"),
        "orchestrator_profile": row.get("orchestrator_profile"),
        "current_milestone_id": row.get("current_milestone_id"),
        "command": row.get("command"),
    }
