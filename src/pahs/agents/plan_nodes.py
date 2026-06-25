"""LangGraph nodes for plan validation and phase execution."""

from __future__ import annotations

from pahs.graph.state import PAHSState
from pahs.planning.orchestrator_planner import plan_fallback_from_context
from pahs.planning.plan_executor import execute_phase, format_plan_progress, plan_is_complete
from pahs.planning.schema import ExecutionPlan
from pahs.planning.step_router import sanitize_plan, validation_report
from pahs.storage import db


def plan_validate_node(state: PAHSState) -> dict:
    raw_plan = state.get("execution_plan") or state.get("plan") or {}
    fallback = plan_fallback_from_context(
        state["user_command"],
        worker=state.get("worker", "creator"),
        execution_mode=state.get("execution_mode"),
        external_agent=state.get("external_agent", ""),
        complexity_band=state.get("complexity_band", "medium"),
        orchestrator_profile=state.get("orchestrator_profile", "lite"),
        task_type=state.get("task_type", "general_task"),
    )

    try:
        candidate = ExecutionPlan.model_validate(raw_plan)
    except Exception:
        candidate = fallback

    plan = sanitize_plan(candidate, fallback=fallback)
    report = validation_report(plan)

    db.log_event(
        state["run_id"],
        "plan_validated",
        {
            "valid": report["valid"],
            "errors": report.get("errors", []),
            "source": plan.source,
            "phase_count": plan.phase_count(),
            "task_count": plan.task_count(),
        },
    )

    return {
        "execution_plan": plan.to_storage_dict(),
        "plan": plan.to_storage_dict(),
        "plan_phase_index": 0,
        "plan_artifacts": {},
        "review_policy": plan.review_policy,
        "complexity_band": plan.complexity_band,
        "orchestrator_profile": plan.orchestrator_profile,
        "task_type": plan.task_type,
        "worker": plan.primary_worker(),
        "status": "PLAN_VALIDATED",
    }


def execute_plan_phase_node(state: PAHSState) -> dict:
    plan = ExecutionPlan.model_validate(state["execution_plan"])
    phase_index = int(state.get("plan_phase_index", 0))

    if plan_is_complete(plan, phase_index):
        return {
            "status": "PLAN_COMPLETE",
            "milestone_output": _final_plan_output(state, plan),
        }

    result = execute_phase(state, plan, phase_index)
    result["plan_progress"] = format_plan_progress(plan, phase_index)

    db.log_event(
        state["run_id"],
        "plan_phase_executed",
        {
            "phase_index": phase_index,
            "phase_id": plan.phases[phase_index].id,
            "parallel": plan.phases[phase_index].parallel,
            "task_ids": [task.id for task in plan.phases[phase_index].tasks],
            "progress": result.get("plan_progress"),
        },
    )
    return result


def plan_retry_phase_node(state: PAHSState) -> dict:
    idx = int(state.get("plan_phase_index", 0))
    return {
        "plan_phase_index": max(0, idx - 1),
        "retry_count": state.get("retry_count", 0) + 1,
        "status": "RETRYING_PHASE",
    }


def _final_plan_output(state: PAHSState, plan: ExecutionPlan) -> str:
    artifacts = state.get("plan_artifacts") or {}
    if not artifacts:
        return state.get("milestone_output", "")

    lines = [
        "[Plan Complete]",
        f"Intent: {plan.intent_summary}",
        "",
    ]
    for phase in plan.phases:
        key = f"phase:{phase.id}"
        block = artifacts.get(key) or {}
        output = block.get("output") if isinstance(block, dict) else str(block)
        lines.append(f"## {phase.title}")
        lines.append(str(output or "").strip())
        lines.append("")
    return "\n".join(lines).strip()
