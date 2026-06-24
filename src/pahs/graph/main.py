"""Build and run the Week 1 LangGraph."""

from __future__ import annotations

from typing import Any, Literal

from langgraph.graph import END, StateGraph
from langgraph.types import Command, interrupt

from pahs.agents.week1 import creator_node, orchestrator_plan_node, triage_node
from pahs.graph.checkpoints import get_checkpointer
from pahs.graph.state import PAHSState
from pahs.harness.validation import verify_basic_node


def ingest_node(state: PAHSState) -> dict:
    return {"status": "INGESTED"}


def present_milestone_node(state: PAHSState) -> dict:
    presentation = (
        "## Milestone Review | 阶段审核\n\n"
        f"Run: `{state['run_id']}`\n"
        f"Milestone: `{state.get('milestone_id', 'm1_output')}`\n\n"
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
    final_response = (
        "## Final Delivery | 最终交付\n\n"
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


def route_after_verify(state: PAHSState) -> Literal["present", "creator"]:
    if state.get("validation_passed"):
        return "present"
    return "creator"


def route_after_milestone_review(state: PAHSState) -> Literal["final_present", "creator"]:
    text = state.get("user_milestone_review", "").strip().lower()
    approved = text in {"approved", "approve", "ok", "pass", "通过", "好", "可以", "yes"}
    if approved:
        return "final_present"
    return "creator"


def build_graph():
    graph = StateGraph(PAHSState)

    graph.add_node("ingest", ingest_node)
    graph.add_node("triage_score", triage_node)
    graph.add_node("orchestrator_plan", orchestrator_plan_node)
    graph.add_node("creator_execute", creator_node)
    graph.add_node("verify_basic", verify_basic_node)
    graph.add_node("present_milestone", present_milestone_node)
    graph.add_node("milestone_human_review", milestone_human_review_node)
    graph.add_node("final_present", final_present_node)
    graph.add_node("final_feedback_request", final_feedback_node)

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "triage_score")
    graph.add_edge("triage_score", "orchestrator_plan")
    graph.add_edge("orchestrator_plan", "creator_execute")
    graph.add_edge("creator_execute", "verify_basic")
    graph.add_conditional_edges(
        "verify_basic",
        route_after_verify,
        {"present": "present_milestone", "creator": "creator_execute"},
    )
    graph.add_edge("present_milestone", "milestone_human_review")
    graph.add_conditional_edges(
        "milestone_human_review",
        route_after_milestone_review,
        {"final_present": "final_present", "creator": "creator_execute"},
    )
    graph.add_edge("final_present", "final_feedback_request")
    graph.add_edge("final_feedback_request", END)

    return graph.compile(checkpointer=get_checkpointer())


def graph_config(run_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id}}
