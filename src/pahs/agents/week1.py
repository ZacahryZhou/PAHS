"""Week 1/2 agent stubs with Week 4+ routing and DeepSeek support."""

from __future__ import annotations

from pahs.config_loader import review_policy_for_band
from pahs.graph.state import PAHSState
from pahs.planning.orchestrator_planner import build_execution_plan
from pahs.planning.task_context import effective_task_prompt
from pahs.providers.mock import mock_plan
from pahs.providers.router import llm_complete
from pahs.routing.cost_estimator import estimate_run_cost, record_cost_event
from pahs.routing.llm_router import route_model
from pahs.routing.standards_loader import load_standards_for_task
from pahs.routing.task_classifier import classify_command
from pahs.storage import db


def triage_node(state: PAHSState) -> dict:
    classified = classify_command(state["user_command"], run_id=state["run_id"])
    band = classified["complexity_band"]
    db.log_event(
        state["run_id"],
        "triage_routing",
        {
            "routing_context": classified["routing_context"],
            "task_type": classified["task_type"],
            "worker": classified["worker"],
            "execution_mode": classified["execution_mode"],
        },
    )
    external_agent = ""
    if classified["worker"] == "external":
        external_agent = classified["execution_mode"] or ""
    return {
        "triage_result": classified["triage_result"],
        "routing_context": classified["routing_context"],
        "task_type": classified["task_type"],
        "orchestrator_profile": classified["orchestrator_profile"],
        "complexity_band": band,
        "worker": classified["worker"],
        "execution_mode": classified["execution_mode"],
        "external_agent": external_agent,
        "review_policy": review_policy_for_band(band),
    }


def orchestrator_plan_node(state: PAHSState) -> dict:
    profile = state.get("orchestrator_profile", "lite")
    triage = state.get("triage_result", {})
    routing_context = state.get("routing_context", {})
    task_type = state.get("task_type", "general_task")

    execution_plan = build_execution_plan(
        state["user_command"],
        routing_context=routing_context,
        triage_result=triage,
        worker=state.get("worker", "creator"),
        execution_mode=state.get("execution_mode"),
        external_agent=state.get("external_agent", ""),
        complexity_band=state.get("complexity_band", "medium"),
        orchestrator_profile=profile,
        task_type=task_type,
        run_id=state["run_id"],
        prefer_llm=True,
    )

    routing_decision = route_model(routing_context)
    cost_estimate = estimate_run_cost(routing_context, routing_decision)
    standards = load_standards_for_task(execution_plan.task_type)

    plan = mock_plan(state["user_command"], profile, triage)
    plan["execution_plan"] = execution_plan.to_storage_dict()
    plan["intent_summary"] = execution_plan.intent_summary
    plan["plan_source"] = execution_plan.source
    plan["routing_decision"] = routing_decision
    plan["cost_estimate"] = cost_estimate
    plan["standards_paths"] = standards["paths"]
    plan["estimated_cost_usd"] = cost_estimate["estimated_cost_usd"]
    plan["worker"] = execution_plan.primary_worker()

    milestone = plan["milestones"][0]
    milestone["id"] = execution_plan.phases[0].id
    milestone["title"] = execution_plan.phases[0].title

    db.update_run(
        state["run_id"],
        orchestrator_profile=profile,
        current_milestone_id=milestone["id"],
        plan_json=plan,
    )
    record_cost_event(
        state["run_id"],
        phase="pre_execution",
        estimated=cost_estimate,
    )
    db.log_event(
        state["run_id"],
        "orchestrator_plan_created",
        {
            "execution_plan": execution_plan.to_storage_dict(),
            "plan_source": execution_plan.source,
            "phase_count": execution_plan.phase_count(),
            "task_count": execution_plan.task_count(),
            "routing_decision": routing_decision,
            "cost_estimate": cost_estimate,
        },
    )

    worker = execution_plan.primary_worker()
    first_task = execution_plan.phases[0].tasks[0]
    execution_mode = first_task.execution_mode or state.get("execution_mode")
    external_agent = first_task.external_agent or state.get("external_agent", "")
    if worker == "external" and external_agent:
        execution_mode = external_agent

    return {
        "plan": plan,
        "execution_plan": execution_plan.to_storage_dict(),
        "milestone_id": milestone["id"],
        "worker": worker,
        "execution_mode": execution_mode,
        "external_agent": external_agent,
        "routing_decision": routing_decision,
        "cost_estimate": cost_estimate,
        "standards_loaded": standards["paths"],
        "review_policy": execution_plan.review_policy,
        "status": "PLANNED",
    }


def creator_node(state: PAHSState) -> dict:
    model = (state.get("routing_decision") or {}).get("selected_model", "deepseek-chat")
    output = llm_complete(
        system=(
            "You are PAHS Creator. Write the deliverable requested by the user. "
            "Be clear, useful, and concise unless the user asks for length."
        ),
        user=effective_task_prompt(state),
        model=model,
        run_id=state["run_id"],
        phase="creator",
    )
    rules = state.get("loaded_rules", [])
    if rules:
        output += "\n\n[Harness] Loaded rules:\n- " + "\n- ".join(rules)
    tools = state.get("tools_available", [])
    if tools:
        output += "\n[Harness] Approved tools: " + ", ".join(tools)
    standards = state.get("standards_loaded", [])
    if standards:
        output += "\n[Harness] Standards: " + ", ".join(standards)
    output += f"\n[Harness] Routed model: {model}"
    return {
        "milestone_output": output,
        "status": "EXECUTED",
    }
