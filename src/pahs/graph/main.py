"""Build and run the PAHS LangGraph with Week 2/3 Harness layers."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from pahs.agents.executor import executor_node
from pahs.agents.external import external_agent_node
from pahs.agents.searcher import searcher_node
from pahs.agents.week1 import creator_node, orchestrator_plan_node, triage_node
from pahs.config_loader import budget_config
from pahs.graph.checkpoints import get_checkpointer
from pahs.graph.state import PAHSState
from pahs.harness.budget import BudgetManager
from pahs.harness.environment import EnvironmentMonitor
from pahs.harness.rules import RuleEngine
from pahs.harness.tools import list_tools_for_agent
from pahs.harness.validation import verify_pipeline_node
from pahs.routing.cost_estimator import record_cost_event
from pahs.routing.no_progress import detect_no_progress, output_fingerprint
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
    worker = state.get("worker", "creator")
    execution_mode = state.get("execution_mode")
    loaded = list(state.get("loaded_rules", []))

    if worker == "executor" and execution_mode:
        pack = _rule_engine.load_for_mode(execution_mode)
        scope = f"mode:{execution_mode}"
    else:
        pack = _rule_engine.load_for_agent(worker)
        scope = worker

    tools = [tool.name for tool in list_tools_for_agent(worker)]
    loaded.extend(pack.paths)
    db.log_event(
        state["run_id"],
        "rules_loaded",
        {"scope": scope, "paths": pack.paths, "tools": tools, "worker": worker},
    )
    return {
        "loaded_rules": loaded,
        "active_agent": worker,
        "tools_available": tools,
        "status": "TARGET_RULES_LOADED",
    }


def env_precheck_node(state: PAHSState) -> dict:
    worker = state.get("worker", "creator")
    budget = BudgetManager(state["run_id"])
    monitor = EnvironmentMonitor(budget)
    result = monitor.precheck(state, step_name=f"{worker}_execute")
    db.log_event(state["run_id"], "environment_precheck", result.get("harness_event"))
    if result.get("harness_event", {}).get("downgraded"):
        db.log_event(
            state["run_id"],
            "routing_downgrade",
            {
                "routing_decision": result.get("routing_decision"),
                "cost_estimate": result.get("cost_estimate"),
            },
        )
    return {
        "env_check_passed": result["env_check_passed"],
        "env_check_message": result["env_check_message"],
        "budget_snapshot": result["budget_snapshot"],
        "routing_decision": result.get("routing_decision", state.get("routing_decision")),
        "cost_estimate": result.get("cost_estimate", state.get("cost_estimate")),
        "status": "ENV_OK" if result["env_check_passed"] else "BLOCKED_BY_ENV",
    }


def worker_execute_node(state: PAHSState) -> dict:
    worker = state.get("worker", "creator")
    if worker == "external":
        return external_agent_node(state)
    if worker == "searcher":
        return searcher_node(state)
    if worker == "executor":
        return executor_node(state)
    return creator_node(state)


def handle_verify_retry_node(state: PAHSState) -> dict:
    no_progress, reason = detect_no_progress(state)
    if no_progress:
        db.log_event(
            state["run_id"],
            "no_progress_detected",
            {"reason": reason, "retry_count": state.get("retry_count", 0)},
        )
        return {
            "no_progress_detected": True,
            "validation_message": reason,
            "status": "NO_PROGRESS",
        }

    retry_count = state.get("retry_count", 0) + 1
    db.log_event(
        state["run_id"],
        "validation_retry",
        {"retry_count": retry_count, "reason": state.get("validation_message")},
    )
    return {
        "retry_count": retry_count,
        "last_validation_message": state.get("validation_message", ""),
        "last_output_fingerprint": output_fingerprint(state.get("milestone_output", "")),
        "no_progress_detected": False,
        "status": "RETRYING",
    }


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
    model = (state.get("routing_decision") or {}).get("selected_model", "unknown")
    estimate = state.get("cost_estimate") or {}
    presentation = (
        "## Milestone Review | 阶段审核\n\n"
        f"Run: `{state['run_id']}`\n"
        f"Worker: `{state.get('worker', 'creator')}`\n"
        f"Mode: `{state.get('execution_mode') or 'none'}`\n"
        f"Model: `{model}`\n"
        f"Est. cost: `${estimate.get('estimated_cost_usd', 0):.6f}`\n"
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
        f"Worker: `{state.get('worker', 'creator')}`\n"
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
    budget_snapshot = state.get("budget_snapshot") or {}
    actual = {
        "tokens": budget_snapshot.get("tokens_used", 0),
        "cost_usd": budget_snapshot.get("cost_usd", 0.0),
    }
    record_cost_event(
        state["run_id"],
        phase="post_run",
        estimated=state.get("cost_estimate") or {},
        actual=actual,
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


def route_after_milestone_review(state: PAHSState) -> Literal["final_present", "retry_worker"]:
    text = state.get("user_milestone_review", "").strip().lower()
    approved = text in {"approved", "approve", "ok", "pass", "通过", "好", "可以", "yes"}
    if approved:
        return "final_present"
    return "retry_worker"


def route_after_retry(state: PAHSState) -> Literal["retry", "failed"]:
    if state.get("no_progress_detected"):
        return "failed"
    return "retry"


def build_graph():
    graph = StateGraph(PAHSState)

    graph.add_node("ingest", ingest_node)
    graph.add_node("load_global_rules", load_global_rules_node)
    graph.add_node("triage_score", triage_node)
    graph.add_node("orchestrator_plan", orchestrator_plan_node)
    graph.add_node("env_precheck", env_precheck_node)
    graph.add_node("load_target_rules", load_target_rules_node)
    graph.add_node("worker_execute", worker_execute_node)
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
    graph.add_edge("load_target_rules", "worker_execute")
    graph.add_edge("worker_execute", "verify_pipeline")
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
    graph.add_conditional_edges(
        "handle_verify_retry",
        route_after_retry,
        {"retry": "worker_execute", "failed": "failed_end"},
    )
    graph.add_edge("present_milestone", "milestone_human_review")
    graph.add_conditional_edges(
        "milestone_human_review",
        route_after_milestone_review,
        {"final_present": "final_present", "retry_worker": "load_target_rules"},
    )
    graph.add_edge("final_present", "final_feedback_request")
    graph.add_edge("final_feedback_request", END)
    graph.add_edge("failed_end", END)
    graph.add_edge("blocked_end", END)

    return graph.compile(checkpointer=get_checkpointer())


def graph_config(run_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id}}
