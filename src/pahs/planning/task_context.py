"""Task prompt helpers for plan-driven execution."""

from __future__ import annotations

from typing import Any

from pahs.graph.state import PAHSState
from pahs.planning.schema import PlanTask, TaskArtifact


def effective_task_prompt(state: PAHSState) -> str:
    return str(
        state.get("task_prompt")
        or state.get("user_milestone_review", "").strip()
        or state["user_command"]
    )


def build_task_prompt(
    task: PlanTask,
    *,
    user_command: str,
    artifacts: dict[str, Any],
) -> str:
    parts = [
        f"Overall user request:\n{user_command}",
        f"\nYour task ({task.id}):\n{task.goal}",
    ]

    if task.inputs:
        parts.append(f"\nTask inputs:\n{_format_mapping(task.inputs)}")

    if task.inputs_from:
        upstream_blocks: list[str] = []
        for task_id in task.inputs_from:
            artifact = artifacts.get(task_id)
            if isinstance(artifact, dict):
                upstream_blocks.append(
                    f"[{task_id}]\n{artifact.get('output', '')}"
                )
        if upstream_blocks:
            parts.append("\nUpstream task outputs:\n" + "\n\n".join(upstream_blocks))

    return "\n".join(parts).strip()


def _format_mapping(data: dict[str, Any]) -> str:
    lines = []
    for key, value in data.items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines)


def artifact_from_result(
    task: PlanTask,
    *,
    phase_id: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    artifact = TaskArtifact(
        task_id=task.id,
        phase_id=phase_id,
        worker=task.worker,
        goal=task.goal,
        output=str(result.get("milestone_output") or ""),
        sources=list(result.get("sources") or []),
        metadata={
            "tool": task.tool,
            "execution_mode": task.execution_mode,
            "external_agent": task.external_agent,
            "search_provider": result.get("search_provider"),
        },
    )
    return artifact.to_storage_dict()
