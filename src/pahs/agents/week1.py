"""Week 1 agent stubs."""

from __future__ import annotations

from pahs.graph.state import PAHSState
from pahs.providers.mock import mock_creator_output, mock_plan, mock_triage


def triage_node(state: PAHSState) -> dict:
    command = state["user_command"]
    triage = mock_triage(command)
    return {
        "triage_result": triage,
        "orchestrator_profile": triage["recommended_orchestrator"],
    }


def orchestrator_plan_node(state: PAHSState) -> dict:
    profile = state.get("orchestrator_profile", "lite")
    triage = state.get("triage_result", {})
    plan = mock_plan(state["user_command"], profile, triage)
    milestone = plan["milestones"][0]
    return {
        "plan": plan,
        "milestone_id": milestone["id"],
        "status": "PLANNED",
    }


def creator_node(state: PAHSState) -> dict:
    output = mock_creator_output(state["user_command"])
    return {
        "milestone_output": output,
        "status": "EXECUTED",
    }
