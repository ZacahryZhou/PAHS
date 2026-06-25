"""Week 1/2 agent stubs with Harness-aware planning."""

from __future__ import annotations

from pahs.config_loader import review_policy_for_band
from pahs.graph.state import PAHSState
from pahs.providers.mock import mock_creator_output, mock_plan, mock_triage
from pahs.storage import db


def triage_node(state: PAHSState) -> dict:
    command = state["user_command"]
    triage = mock_triage(command)
    band = triage.get("complexity_band", "simple")
    return {
        "triage_result": triage,
        "orchestrator_profile": triage["recommended_orchestrator"],
        "complexity_band": band,
        "review_policy": review_policy_for_band(band),
    }


def orchestrator_plan_node(state: PAHSState) -> dict:
    profile = state.get("orchestrator_profile", "lite")
    triage = state.get("triage_result", {})
    plan = mock_plan(state["user_command"], profile, triage)
    milestone = plan["milestones"][0]
    db.update_run(
        state["run_id"],
        orchestrator_profile=profile,
        current_milestone_id=milestone["id"],
        plan_json=plan,
    )
    return {
        "plan": plan,
        "milestone_id": milestone["id"],
        "status": "PLANNED",
    }


def creator_node(state: PAHSState) -> dict:
    output = mock_creator_output(state["user_command"])
    rules = state.get("loaded_rules", [])
    if rules:
        output += "\n\n[Harness] Loaded rules:\n- " + "\n- ".join(rules)
    tools = state.get("tools_available", [])
    if tools:
        output += "\n[Harness] Approved tools: " + ", ".join(tools)
    return {
        "milestone_output": output,
        "status": "EXECUTED",
    }
