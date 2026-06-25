"""Execute ExecutionPlan phases and tasks."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from pahs.agents.executor import executor_node
from pahs.agents.external import external_agent_node
from pahs.agents.searcher import searcher_node
from pahs.agents.week1 import creator_node
from pahs.graph.state import PAHSState
from pahs.planning.schema import ExecutionPlan, PlanPhase, PlanTask
from pahs.planning.task_context import artifact_from_result, build_task_prompt


def _phase_dependencies_met(phase: PlanPhase, artifacts: dict[str, Any]) -> bool:
    for dep in phase.depends_on:
        key = f"phase:{dep}"
        if key not in artifacts and dep not in artifacts:
            return False
    return True


def _run_task_worker(state: PAHSState, task: PlanTask, prompt: str) -> dict[str, Any]:
    task_state: PAHSState = {
        **state,
        "task_prompt": prompt,
        "worker": task.worker,
        "current_task": task.model_dump(),
        "execution_mode": task.execution_mode or state.get("execution_mode"),
        "external_agent": task.external_agent or state.get("external_agent", ""),
    }
    if task.worker == "external":
        if task.external_agent:
            task_state["execution_mode"] = task.external_agent
            task_state["external_agent"] = task.external_agent
        return external_agent_node(task_state)
    if task.worker == "searcher":
        return searcher_node(task_state)
    if task.worker == "executor":
        if task.execution_mode:
            task_state["execution_mode"] = task.execution_mode
        return executor_node(task_state)
    return creator_node(task_state)


def run_plan_task(
    state: PAHSState,
    task: PlanTask,
    *,
    phase_id: str,
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    prompt = build_task_prompt(
        task,
        user_command=state["user_command"],
        artifacts=artifacts,
    )
    result = _run_task_worker(state, task, prompt)
    artifact = artifact_from_result(task, phase_id=phase_id, result=result)
    return {
        "artifact": artifact,
        "result": result,
    }


def _merge_task_result(
    aggregate: dict[str, Any],
    task: PlanTask,
    payload: dict[str, Any],
) -> None:
    result = payload["result"]
    aggregate["artifacts"][task.id] = payload["artifact"]
    aggregate["outputs"].append(result.get("milestone_output", ""))
    if result.get("sources"):
        aggregate["sources"].extend(result["sources"])
    aggregate["last_result"] = result


def execute_phase(
    state: PAHSState,
    plan: ExecutionPlan,
    phase_index: int,
) -> dict[str, Any]:
    phase = plan.phases[phase_index]
    artifacts = dict(state.get("plan_artifacts") or {})

    if not _phase_dependencies_met(phase, artifacts):
        return {
            "status": "PLAN_BLOCKED",
            "validation_passed": False,
            "validation_message": f"Phase `{phase.id}` dependencies not satisfied.",
        }

    aggregate: dict[str, Any] = {
        "artifacts": {},
        "outputs": [],
        "sources": [],
        "last_result": {},
    }

    if phase.parallel and len(phase.tasks) > 1:
        with ThreadPoolExecutor(max_workers=min(4, len(phase.tasks))) as pool:
            futures = {
                pool.submit(run_plan_task, state, task, phase_id=phase.id, artifacts=artifacts): task
                for task in phase.tasks
            }
            for future in as_completed(futures):
                task = futures[future]
                payload = future.result()
                _merge_task_result(aggregate, task, payload)
    else:
        running = dict(artifacts)
        for task in phase.tasks:
            payload = run_plan_task(state, task, phase_id=phase.id, artifacts=running)
            _merge_task_result(aggregate, task, payload)
            running[task.id] = payload["artifact"]

    artifacts.update(aggregate["artifacts"])
    phase_summary = "\n\n---\n\n".join(
        block for block in aggregate["outputs"] if str(block).strip()
    )
    artifacts[f"phase:{phase.id}"] = {
        "phase_id": phase.id,
        "title": phase.title,
        "output": phase_summary,
        "task_ids": [task.id for task in phase.tasks],
    }

    last = aggregate["last_result"]
    primary_task = phase.tasks[-1]
    return {
        "plan_artifacts": artifacts,
        "plan_phase_index": phase_index + 1,
        "current_phase_id": phase.id,
        "milestone_id": f"{phase.id}",
        "milestone_output": phase_summary,
        "worker": primary_task.worker,
        "execution_mode": primary_task.execution_mode or last.get("execution_mode"),
        "external_agent": primary_task.external_agent or last.get("external_agent", ""),
        "sources": aggregate["sources"],
        "search_provider": last.get("search_provider"),
        "search_step": last.get("search_step"),
        "status": "PHASE_EXECUTED",
    }


def plan_is_complete(plan: ExecutionPlan, phase_index: int) -> bool:
    return phase_index >= plan.phase_count()


def format_plan_progress(plan: ExecutionPlan, phase_index: int) -> str:
    total = plan.phase_count()
    current = min(phase_index + 1, total)
    return f"Plan progress: phase {current}/{total}"
