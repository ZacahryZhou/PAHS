"""Step Router — structural plan validation (scoring deferred to later phase)."""

from __future__ import annotations

from typing import Any

from pahs.external.registry import get_external_agent
from pahs.harness.tools import all_approved_tools
from pahs.planning.schema import ExecutionPlan, PlanPhase, PlanTask

_VALID_WORKERS = {"searcher", "creator", "executor", "external"}


def validate_plan(plan: ExecutionPlan) -> tuple[bool, list[str]]:
    """Validate plan structure and capability references. No scoring yet."""
    errors: list[str] = []
    approved_tools = set(all_approved_tools().keys())
    phase_ids = {phase.id for phase in plan.phases}
    task_ids: set[str] = set()

    for phase in plan.phases:
        errors.extend(_validate_phase(phase, phase_ids, task_ids, approved_tools))

    if not errors and not plan.phases:
        errors.append("plan has no phases")

    return not errors, errors


def _validate_phase(
    phase: PlanPhase,
    phase_ids: set[str],
    task_ids: set[str],
    approved_tools: set[str],
) -> list[str]:
    errors: list[str] = []
    for dep in phase.depends_on:
        if dep not in phase_ids:
            errors.append(f"phase `{phase.id}` depends on unknown phase `{dep}`")

    local_ids: set[str] = set()
    for task in phase.tasks:
        if task.id in task_ids or task.id in local_ids:
            errors.append(f"duplicate task id `{task.id}`")
        local_ids.add(task.id)
        task_ids.add(task.id)
        errors.extend(_validate_task(task, approved_tools))

        for upstream in task.inputs_from:
            if upstream not in task_ids - {task.id}:
                errors.append(f"task `{task.id}` inputs_from unknown task `{upstream}`")

    return errors


def _validate_task(task: PlanTask, approved_tools: set[str]) -> list[str]:
    errors: list[str] = []
    if task.worker not in _VALID_WORKERS:
        errors.append(f"task `{task.id}` has invalid worker `{task.worker}`")

    if task.worker == "external":
        agent_name = task.external_agent or task.tool
        if not agent_name:
            errors.append(f"task `{task.id}` external worker missing external_agent")
        elif get_external_agent(agent_name) is None:
            errors.append(f"task `{task.id}` references disabled/unknown external `{agent_name}`")

    if task.tool and task.tool not in approved_tools and task.worker != "external":
        if task.worker != "executor" or task.tool not in approved_tools:
            errors.append(f"task `{task.id}` references unknown tool `{task.tool}`")

    if task.worker == "executor" and task.execution_mode not in {
        None,
        "CODE",
        "ANALYSIS",
        "DEEP_THINK",
    }:
        errors.append(f"task `{task.id}` has invalid execution_mode `{task.execution_mode}`")

    return errors


def sanitize_plan(plan: ExecutionPlan, *, fallback: ExecutionPlan) -> ExecutionPlan:
    """Return plan if valid, otherwise fallback."""
    ok, errors = validate_plan(plan)
    if ok:
        return plan
    sanitized = fallback.model_copy(deep=True)
    sanitized.source = "sanitized_fallback"
    sanitized.intent_summary = plan.intent_summary or sanitized.intent_summary
    return sanitized


def validation_report(plan: ExecutionPlan) -> dict[str, Any]:
    ok, errors = validate_plan(plan)
    return {
        "valid": ok,
        "errors": errors,
        "phase_count": plan.phase_count(),
        "task_count": plan.task_count(),
    }
