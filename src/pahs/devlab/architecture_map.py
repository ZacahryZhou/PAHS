"""Map run_events to LangGraph / architecture nodes for Dev Lab UI."""

from __future__ import annotations

from typing import Any

# Ordered LangGraph pipeline nodes (Path A)
GRAPH_NODES: list[dict[str, str]] = [
    {"id": "ingest", "label": "Ingest", "layer": "gateway", "label_zh": "接收任务"},
    {"id": "load_global_rules", "label": "Global Rules", "layer": "harness", "label_zh": "全局规则"},
    {"id": "triage_score", "label": "Triage", "layer": "routing", "label_zh": "① 分诊 Triage"},
    {"id": "orchestrator_plan", "label": "Orchestrator", "layer": "orchestrator", "label_zh": "🎯 编排任务表"},
    {"id": "plan_validate", "label": "Plan Validate", "layer": "routing", "label_zh": "② 计划校验"},
    {"id": "env_precheck", "label": "Env Precheck", "layer": "harness", "label_zh": "环境/预算"},
    {"id": "load_target_rules", "label": "Target Rules", "layer": "harness", "label_zh": "专员规则"},
    {"id": "execute_plan_phase", "label": "Execute Phase", "layer": "execution", "label_zh": "执行 Phase"},
    {"id": "search_router", "label": "Search Router", "layer": "routing", "label_zh": "③ Search 路由"},
    {"id": "verify_pipeline", "label": "Verify", "layer": "harness", "label_zh": "质量验证"},
    {"id": "milestone_review", "label": "Milestone Review", "layer": "human", "label_zh": "⏸ 人工审核"},
    {"id": "final_present", "label": "Final Delivery", "layer": "human", "label_zh": "最终交付"},
    {"id": "learner", "label": "Learner", "layer": "learning", "label_zh": "Learner 学习"},
]

NODE_ORDER = [node["id"] for node in GRAPH_NODES]

EVENT_TO_NODE: dict[str, str] = {
    "devlab_run_started": "ingest",
    "rules_loaded": "load_global_rules",
    "triage_routing": "triage_score",
    "orchestrator_plan_created": "orchestrator_plan",
    "plan_validated": "plan_validate",
    "environment_precheck": "env_precheck",
    "routing_decision": "load_target_rules",
    "plan_phase_executed": "execute_plan_phase",
    "search_route": "search_router",
    "validation_retry": "verify_pipeline",
    "validation_failed": "verify_pipeline",
    "devlab_interrupt": "milestone_review",
    "devlab_run_completed": "final_present",
    "learner_proposals_created": "learner",
    "cost_tracking": "env_precheck",
}

LAYER_COLORS: dict[str, str] = {
    "gateway": "#64748b",
    "routing": "#f59e0b",
    "orchestrator": "#3b82f6",
    "harness": "#8b5cf6",
    "execution": "#22c55e",
    "human": "#ec4899",
    "learning": "#06b6d4",
}


def _rules_loaded_node(payload: dict[str, Any]) -> str:
    scope = str(payload.get("scope", ""))
    if scope == "global":
        return "load_global_rules"
    return "load_target_rules"


def _mark_node_done(states: dict[str, str], node_id: str) -> None:
    if node_id not in NODE_ORDER:
        return
    idx = NODE_ORDER.index(node_id)
    for i in range(0, idx + 1):
        nid = NODE_ORDER[i]
        if states.get(nid) != "failed":
            states[nid] = "done"


def build_progress(
    events: list[dict[str, Any]],
    *,
    run_status: str | None = None,
    waiting_review: bool = False,
) -> dict[str, Any]:
    """Derive per-node status from run_events."""
    states: dict[str, str] = {node_id: "pending" for node_id in NODE_ORDER}
    timeline: list[dict[str, Any]] = []

    for event in events:
        event_type = str(event.get("event_type", ""))
        payload = event.get("payload") or {}
        node_id = EVENT_TO_NODE.get(event_type)
        if event_type == "rules_loaded":
            node_id = _rules_loaded_node(payload)
        if not node_id:
            timeline.append(
                {
                    "event_type": event_type,
                    "node_id": None,
                    "created_at": event.get("created_at"),
                    "summary": _summarize_event(event_type, payload),
                }
            )
            continue

        _mark_node_done(states, node_id)
        timeline.append(
            {
                "event_type": event_type,
                "node_id": node_id,
                "created_at": event.get("created_at"),
                "summary": _summarize_event(event_type, payload),
            }
        )

    active_node = _infer_active_node(states, run_status, waiting_review)
    if active_node and states.get(active_node) == "pending":
        states[active_node] = "active"

    if waiting_review:
        states["milestone_review"] = "waiting"

    if run_status in {"FAILED", "BLOCKED"}:
        for node_id, status in states.items():
            if status == "active":
                states[node_id] = "failed"

    nodes = []
    for meta in GRAPH_NODES:
        nodes.append(
            {
                **meta,
                "color": LAYER_COLORS.get(meta["layer"], "#94a3b8"),
                "status": states.get(meta["id"], "pending"),
            }
        )

    return {
        "nodes": nodes,
        "timeline": timeline,
        "active_node": active_node,
        "run_status": run_status,
        "waiting_review": waiting_review,
    }


def _infer_active_node(
    states: dict[str, str],
    run_status: str | None,
    waiting_review: bool,
) -> str | None:
    if waiting_review or run_status == "AWAITING_REVIEW":
        return "milestone_review"
    if run_status == "AWAITING_FINAL_FEEDBACK":
        return "final_present"
    if run_status == "COMPLETED":
        return None
    for node_id in NODE_ORDER:
        if states.get(node_id) == "pending":
            return node_id
    return None


def _summarize_event(event_type: str, payload: dict[str, Any]) -> str:
    if event_type == "triage_routing":
        worker = payload.get("worker") or (payload.get("routing_context") or {}).get("worker")
        return f"Triage → worker={worker}"
    if event_type == "orchestrator_plan_created":
        return (
            f"Plan: {payload.get('phase_count', '?')} phases, "
            f"{payload.get('task_count', '?')} tasks"
        )
    if event_type == "plan_validated":
        return f"Valid={payload.get('valid')} source={payload.get('source')}"
    if event_type == "plan_phase_executed":
        return (
            f"Phase `{payload.get('phase_id')}` "
            f"tasks={payload.get('task_ids', [])}"
        )
    if event_type == "devlab_interrupt":
        return f"Paused: {payload.get('review_type', 'review')}"
    if event_type == "environment_precheck":
        return "Env/budget precheck"
    if event_type == "rules_loaded":
        return f"Rules loaded: {payload.get('scope', '?')}"
    if event_type == "learner_proposals_created":
        return f"Learner proposals: {payload.get('count', 0)}"
    return event_type.replace("_", " ")
