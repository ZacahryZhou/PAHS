"""Build and run the PAHS LangGraph with Week 2 Harness layers."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from pahs.agents.week1 import creator_node, orchestrator_plan_node, triage_node
from pahs.config_loader import budget_config
from pahs.graph.checkpoints import get_checkpointer
from pahs.graph.state import PAHSState
from pahs.harness.budget import BudgetManager
from pahs.harness.environment import EnvironmentMonitor
from pahs.harness.rules import RuleEngine
from pahs.harness.tools import list_tools_for_agent
from pahs.harness.validation import verify_pipeline_node
from pahs.storage import db

_rule_engine = RuleEngine()


def ingest_node(state: PAHSState) -> dict:
    return {"status": "INGESTED", "retry_count": state.get("retry_count", 0)}


def load_global_rules_node(state: PAHSState) -> dict:
    pack = _rule_engine.load_global()
    db.log_event(
        state["run_id"],
        "rules_loaded",
        {"scope": "global", "paths": pack.paths},
    )
    return {
        "loaded_rules": pack.paths,
        "status": "GLOBAL_RULES_LOADED",
    }


def load_target_rules_node(state: PAHSState) -> dict:
    pack = _rule_engine.load_for_agent("creator")
    tools = [tool.name for tool in list_tools_for_agent("creator")]
    loaded = list(state.get("loaded_rules", [])) + pack.paths
    db.log_event(
        state["run_id"],
        "rules_loaded",
        {"scope": "creator", "paths": pack.paths, "tools": tools},
    )
    return {
        "loaded_rules": loaded,
        "active_agent": "creator",
        "tools_available": tools,
        "status": "TARGET_RULES_LOADED",
    }


def env_precheck_node(state: PAHSState) -> dict:
    budget = BudgetManager(state["run_id"])
    monitor = EnvironmentMonitor(budget)
    result = monitor.precheck(state, step_name="creator_execute")
    db.log_event(state["run_id"], "environment_precheck", result.get("harness_event"))
    return {
        "env_check_passed": result["env_check_passed"],
        "env_check_message": result["env_check_message"],
        "budget_snapshot": result["budget_snapshot"],
        "status": "ENV_OK" if result["env_check_passed"] else "BLOCKED_BY_ENV",
    }


def handle_verify_retry_node(state: PAHSState) -> dict:
    retry_count = state.get("retry_count", 0) + 1
    db.log_event(
        state["run_id"],
        "validation_retry",
        {"retry_count": retry_count, "reason": state.get("validation_message")},
    )
    return {"retry_count": retry_count, "status": "RETRYING"}


def failed_end_node(state: PAHSState) -> dict:
    db.log_event(
        state["run_id"],
        "validation_failed",
        {"message": state.get("validation_message"), "retry_count": state.get("retry_count", 0)},
    )
    db.update_run(state["run_id"], status="FAILED")
    return {"status": "FAILED"}


def blocked_end_node(state: PAHSState) -> dict:
    db.update_run(state["run_id"], status="BLOCKED")
    return {"status": "BLOCKED"}


def present_milestone_node(state: PAHSState) -> dict:
    presentation = (
        "## Milestone Review | 阶段审核\n\n"
        f"Run: `{state['run_id']}`\n"
        f"Milestone: `{state.get('milestone_id', 'm1_output')}`\n"
        f"Complexity: `{state.get('complexity_band', 'unknown')}`\n\n"
        f"{state.get('milestone_output', '')}\n\n"
        "Reply with `approved` / `通过` to continue.\n"
        "回复 `approved` / `通过` 继续。"
    )
    return {"presentation": presentation}


def milestone_human_review_node(state: PAHSState) -> dict:
    user_input = interrupt(
        {
            "type": "milestone_review",
            "run_id": state["run_id"],
            "milestone_id": state.get("milestone_id"),
            "presentation": state.get("presentation"),
        }
    )
    return {
        "user_milestone_review": str(user_input),
        "status": "MILESTONE_REVIEWED",
    }


def final_present_node(state: PAHSState) -> dict:
    policy = state.get("review_policy", {})
    final_response = (
        "## Final Delivery | 最终交付\n\n"
        f"Review policy: `{policy.get('milestone_reviews', 'unknown')}`\n\n"
        f"{state.get('milestone_output', '')}\n\n"
        "Please send final feedback after the run completes.\n"
        "任务完成后请提供总反馈。"
    )
    return {"final_response": final_response, "status": "AWAITING_FINAL_FEEDBACK"}


def final_feedback_node(state: PAHSState) -> dict:
    feedback = interrupt(
        {
            "type": "final_feedback",
            "run_id": state["run_id"],
            "final_response": state.get("final_response"),
        }
    )
    return {
        "user_final_feedback": str(feedback),
        "status": "COMPLETED",
    }


def route_after_env(state: PAHSState) -> Literal["continue", "blocked"]:
    if state.get("env_check_passed") is False:
        return "blocked"
    return "continue"


def route_after_verify(
    state: PAHSState,
) -> Literal["present", "final", "retry", "failed"]:
    if state.get("validation_passed"):
        policy = state.get("review_policy", {})
        if policy.get("milestone_reviews") == "final_only":
            return "final"
        return "present"

    max_retries = int(
        budget_config().get("budget", {}).get("per_step", {}).get("max_retries", 2)
    )
    if state.get("retry_count", 0) < max_retries:
        return "retry"
    return "failed"


def route_after_milestone_review(state: PAHSState) -> Literal["final_present", "creator"]:
    text = state.get("user_milestone_review", "").strip().lower()
    approved = text in {"approved", "approve", "ok", "pass", "通过", "好", "可以", "yes"}
    if approved:
        return "final_present"
    return "creator"


def build_graph():
    graph = StateGraph(PAHSState)

    graph.add_node("ingest", ingest_node)
    graph.add_node("load_global_rules", load_global_rules_node)
    graph.add_node("triage_score", triage_node)
    graph.add_node("orchestrator_plan", orchestrator_plan_node)
    graph.add_node("env_precheck", env_precheck_node)
    graph.add_node("load_target_rules", load_target_rules_node)
    graph.add_node("creator_execute", creator_node)
    graph.add_node("verify_pipeline", verify_pipeline_node)
    graph.add_node("handle_verify_retry", handle_verify_retry_node)
    graph.add_node("failed_end", failed_end_node)
    graph.add_node("blocked_end", blocked_end_node)
    graph.add_node("present_milestone", present_milestone_node)
    graph.add_node("milestone_human_review", milestone_human_review_node)
    graph.add_node("final_present", final_present_node)
    graph.add_node("final_feedback_request", final_feedback_node)

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "load_global_rules")
    graph.add_edge("load_global_rules", "triage_score")
    graph.add_edge("triage_score", "orchestrator_plan")
    graph.add_edge("orchestrator_plan", "env_precheck")
    graph.add_conditional_edges(
        "env_precheck",
        route_after_env,
        {"continue": "load_target_rules", "blocked": "blocked_end"},
    )
    graph.add_edge("load_target_rules", "creator_execute")
    graph.add_edge("creator_execute", "verify_pipeline")
    graph.add_conditional_edges(
        "verify_pipeline",
        route_after_verify,
        {
            "present": "present_milestone",
            "final": "final_present",
            "retry": "handle_verify_retry",
            "failed": "failed_end",
        },
    )
    graph.add_edge("handle_verify_retry", "creator_execute")
    graph.add_edge("present_milestone", "milestone_human_review")
    graph.add_conditional_edges(
        "milestone_human_review",
        route_after_milestone_review,
        {"final_present": "final_present", "creator": "load_target_rules"},
    )
    graph.add_edge("final_present", "final_feedback_request")
    graph.add_edge("final_feedback_request", END)
    graph.add_edge("failed_end", END)
    graph.add_edge("blocked_end", END)

    return graph.compile(checkpointer=get_checkpointer())


def graph_config(run_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id}}
