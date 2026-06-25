"""Delegate work to a configured external agent such as OpenClaw."""

from __future__ import annotations

from pahs.external.registry import get_external_agent
from pahs.external.runner import format_external_output, run_external_agent
from pahs.graph.state import PAHSState
from pahs.planning.task_context import effective_task_prompt


def external_agent_node(state: PAHSState) -> dict:
    agent_name = state.get("execution_mode") or state.get("external_agent", "")
    prompt = effective_task_prompt(state)

    spec = get_external_agent(agent_name)
    if spec is None:
        return {
            "milestone_output": f"[External Agent] Unknown or disabled agent `{agent_name}`.",
            "status": "EXECUTED",
        }

    try:
        result = run_external_agent(agent_name, prompt, run_id=state["run_id"])
        output = format_external_output(agent_name, spec, result)
    except Exception as exc:
        output = f"[External Agent: {agent_name}] Failed: {exc}"
        result = {"ok": False, "text": str(exc)}

    return {
        "milestone_output": output,
        "external_agent": agent_name,
        "external_result": result,
        "status": "EXECUTED",
    }
