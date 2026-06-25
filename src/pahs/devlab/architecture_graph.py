"""Global architecture graph for Dev Lab (Path A + Path B, branches)."""

from __future__ import annotations

from typing import Any

from pahs.devlab.architecture_map import build_progress as _build_linear_progress
from pahs.devlab.architecture_map import default_progress as _default_linear

# Global graph: positions for SVG (viewBox 0 0 820 720)
ARCHITECTURE_GRAPH: dict[str, Any] = {
    "viewBox": "0 0 820 720",
    "paths": {
        "A": {"label": "Path A · LangGraph 完整团队", "label_en": "Full team pipeline"},
        "B": {"label": "Path B · Telegram 直达", "label_en": "Direct SMAS / PIP"},
    },
    "nodes": [
        {"id": "entry", "label": "用户入口", "sublabel": "CLI / Dev Lab", "path": "common", "x": 400, "y": 28, "w": 120, "h": 36},
        # Path B (left branch)
        {"id": "path_b_router", "label": "intent_router", "sublabel": "Path B", "path": "B", "x": 120, "y": 100, "w": 130, "h": 36},
        {"id": "path_b_direct", "label": "direct_tools", "sublabel": "Path B", "path": "B", "x": 120, "y": 170, "w": 130, "h": 36},
        {"id": "smas", "label": "SMAS", "sublabel": "IG 图文", "path": "B", "x": 40, "y": 250, "w": 100, "h": 32},
        {"id": "pip", "label": "PIP", "sublabel": "短视频", "path": "B", "x": 170, "y": 250, "w": 100, "h": 32},
        # Path A trunk (center-right)
        {"id": "ingest", "label": "Ingest", "sublabel": "gateway", "path": "A", "x": 400, "y": 100, "w": 110, "h": 32},
        {"id": "load_global_rules", "label": "Global Rules", "sublabel": "harness", "path": "A", "x": 400, "y": 150, "w": 110, "h": 32},
        {"id": "triage_score", "label": "Triage", "sublabel": "routing", "path": "A", "x": 400, "y": 200, "w": 110, "h": 32},
        {"id": "orchestrator_plan", "label": "Orchestrator", "sublabel": "任务表", "path": "A", "x": 400, "y": 250, "w": 110, "h": 32},
        {"id": "plan_validate", "label": "Step Router", "sublabel": "校验", "path": "A", "x": 400, "y": 300, "w": 110, "h": 32},
        {"id": "env_precheck", "label": "Env / Budget", "sublabel": "harness", "path": "A", "x": 400, "y": 350, "w": 110, "h": 32},
        {"id": "load_target_rules", "label": "Target Rules", "sublabel": "harness", "path": "A", "x": 400, "y": 400, "w": 110, "h": 32},
        {"id": "execute_plan_phase", "label": "Execute Phase", "sublabel": "execution", "path": "A", "x": 400, "y": 450, "w": 110, "h": 32},
        # Worker branch (Path A)
        {"id": "worker_searcher", "label": "Searcher", "sublabel": "worker", "path": "A", "x": 200, "y": 530, "w": 100, "h": 30},
        {"id": "search_router", "label": "Search Router", "sublabel": "routing", "path": "A", "x": 200, "y": 580, "w": 100, "h": 30},
        {"id": "worker_creator", "label": "Creator", "sublabel": "worker", "path": "A", "x": 330, "y": 530, "w": 100, "h": 30},
        {"id": "worker_executor", "label": "Executor", "sublabel": "worker", "path": "A", "x": 460, "y": 530, "w": 100, "h": 30},
        {"id": "worker_external", "label": "External", "sublabel": "SMAS/PIP", "path": "A", "x": 590, "y": 530, "w": 100, "h": 30},
        # Merge
        {"id": "verify_pipeline", "label": "Verify", "sublabel": "harness", "path": "A", "x": 400, "y": 640, "w": 110, "h": 32},
        {"id": "milestone_review", "label": "人工审核", "sublabel": "human", "path": "A", "x": 550, "y": 640, "w": 100, "h": 32},
        {"id": "final_present", "label": "最终交付", "sublabel": "human", "path": "A", "x": 680, "y": 640, "w": 100, "h": 32},
        {"id": "learner", "label": "Learner", "sublabel": "learning", "path": "A", "x": 680, "y": 580, "w": 100, "h": 30},
    ],
    "edges": [
        {"from": "entry", "to": "path_b_router", "path": "B"},
        {"from": "entry", "to": "ingest", "path": "A"},
        {"from": "path_b_router", "to": "path_b_direct", "path": "B"},
        {"from": "path_b_direct", "to": "smas", "path": "B"},
        {"from": "path_b_direct", "to": "pip", "path": "B"},
        {"from": "ingest", "to": "load_global_rules", "path": "A"},
        {"from": "load_global_rules", "to": "triage_score", "path": "A"},
        {"from": "triage_score", "to": "orchestrator_plan", "path": "A"},
        {"from": "orchestrator_plan", "to": "plan_validate", "path": "A"},
        {"from": "plan_validate", "to": "env_precheck", "path": "A"},
        {"from": "env_precheck", "to": "load_target_rules", "path": "A"},
        {"from": "load_target_rules", "to": "execute_plan_phase", "path": "A"},
        {"from": "execute_plan_phase", "to": "worker_searcher", "path": "A"},
        {"from": "execute_plan_phase", "to": "worker_creator", "path": "A"},
        {"from": "execute_plan_phase", "to": "worker_executor", "path": "A"},
        {"from": "execute_plan_phase", "to": "worker_external", "path": "A"},
        {"from": "worker_searcher", "to": "search_router", "path": "A"},
        {"from": "search_router", "to": "verify_pipeline", "path": "A"},
        {"from": "worker_creator", "to": "verify_pipeline", "path": "A"},
        {"from": "worker_executor", "to": "verify_pipeline", "path": "A"},
        {"from": "worker_external", "to": "verify_pipeline", "path": "A"},
        {"from": "verify_pipeline", "to": "milestone_review", "path": "A"},
        {"from": "milestone_review", "to": "final_present", "path": "A"},
        {"from": "final_present", "to": "learner", "path": "A"},
    ],
}

# Map run_events → graph node ids (extends linear map)
EVENT_TO_GRAPH_NODE: dict[str, str] = {
    "devlab_run_started": "ingest",
    "rules_loaded": "load_global_rules",
    "triage_routing": "triage_score",
    "capability_assessed": "triage_score",
    "orchestrator_plan_created": "orchestrator_plan",
    "plan_validated": "plan_validate",
    "environment_precheck": "env_precheck",
    "routing_decision": "load_target_rules",
    "plan_phase_executed": "execute_plan_phase",
    "search_route": "search_router",
    "validation_retry": "verify_pipeline",
    "validation_failed": "verify_pipeline",
    "devlab_run_failed": "orchestrator_plan",
    "llm_usage": "triage_score",
    "devlab_interrupt": "milestone_review",
    "devlab_run_completed": "final_present",
    "learner_proposals_created": "learner",
}

PATH_A_ORDER: list[str] = [
    "ingest",
    "load_global_rules",
    "triage_score",
    "orchestrator_plan",
    "plan_validate",
    "env_precheck",
    "load_target_rules",
    "execute_plan_phase",
    "worker_searcher",
    "worker_creator",
    "worker_executor",
    "worker_external",
    "search_router",
    "verify_pipeline",
    "milestone_review",
    "final_present",
    "learner",
]


def _rules_node(payload: dict[str, Any]) -> str:
    if str(payload.get("scope", "")) == "global":
        return "load_global_rules"
    return "load_target_rules"


def _worker_from_phase(payload: dict[str, Any]) -> str | None:
    workers = payload.get("workers") or []
    if workers:
        w = workers[0]
        return f"worker_{w}"
    task_ids = payload.get("task_ids") or []
    if not task_ids:
        return None
    return None


def build_graph_progress(
    events: list[dict[str, Any]],
    *,
    run_status: str | None = None,
    waiting_review: bool = False,
    active_path: str = "A",
) -> dict[str, Any]:
    """Build status for each node in the global architecture graph."""
    node_ids = [n["id"] for n in ARCHITECTURE_GRAPH["nodes"]]
    states: dict[str, str] = {nid: "pending" for nid in node_ids}
    timeline: list[dict[str, Any]] = []
    node_details: dict[str, list[dict[str, Any]]] = {nid: [] for nid in node_ids}
    active_workers: set[str] = set()
    run_error: str | None = None

    for event in events:
        et = str(event.get("event_type", ""))
        payload = event.get("payload") or {}
        node_id = EVENT_TO_GRAPH_NODE.get(et)
        if et == "rules_loaded":
            node_id = _rules_node(payload)
        if et == "llm_usage":
            node_id = {
                "triage": "triage_score",
                "orchestrator_plan": "orchestrator_plan",
            }.get(str(payload.get("phase", "")), node_id)
        if et == "plan_phase_executed":
            node_id = "execute_plan_phase"
            for w in payload.get("workers") or []:
                active_workers.add(f"worker_{w}")
            worker = payload.get("worker")
            if worker:
                active_workers.add(f"worker_{worker}")
        if et == "devlab_run_failed":
            node_id = str(payload.get("node_id") or "orchestrator_plan")
            run_error = str(payload.get("error") or "Run failed")
            if node_id in states:
                states[node_id] = "failed"
        if et == "validation_failed":
            node_id = "verify_pipeline"
            states["verify_pipeline"] = "failed"
            run_error = str(payload.get("message") or run_error or "Validation failed")

        summary = et.replace("_", " ")
        if et == "triage_routing":
            summary = f"Triage → {payload.get('worker', '?')}"
        elif et == "capability_assessed":
            gaps = payload.get("gaps") or []
            summary = (
                "Capability OK"
                if not gaps
                else f"Capability gaps: {len(gaps)}"
            )
        elif et == "orchestrator_plan_created":
            summary = f"Plan {payload.get('phase_count')} phases, source={payload.get('plan_source')}"
        elif et == "plan_phase_executed":
            summary = f"Phase {payload.get('phase_id')} workers={payload.get('workers', [])}"
        elif et == "search_route":
            summary = f"Search → {payload.get('provider', '?')}"
            active_workers.add("worker_searcher")
        elif et == "validation_failed":
            summary = f"Verify FAILED: {payload.get('message', '?')}"
        elif et == "validation_retry":
            summary = f"Verify retry #{payload.get('retry_count')}: {payload.get('reason', '')}"
        elif et == "devlab_run_failed":
            summary = f"ERROR: {(payload.get('error') or '')[:160]}"
        elif et == "llm_usage":
            usage = payload.get("usage") or {}
            summary = (
                f"LLM {payload.get('phase')} "
                f"tokens={usage.get('total_tokens', '?')}"
            )
        elif et == "plan_validated":
            summary = f"Valid={payload.get('valid')} errors={payload.get('errors', [])}"

        entry = {
            "id": event.get("id"),
            "event_type": et,
            "node_id": node_id,
            "summary": summary,
            "payload": payload,
            "created_at": event.get("created_at"),
        }
        timeline.append(entry)
        if node_id and node_id in node_details:
            node_details[node_id].append(entry)
        elif et == "plan_phase_executed":
            for w in payload.get("workers") or []:
                wid = f"worker_{w}"
                if wid in node_details:
                    node_details[wid].append(entry)

        if node_id and et not in {"devlab_run_failed", "validation_failed"}:
            _mark_done_graph(states, node_id, PATH_A_ORDER)

    for wid in active_workers:
        if wid in states:
            states[wid] = "done"

    # active node on Path A
    active_node = None
    if waiting_review or run_status == "AWAITING_REVIEW":
        states["milestone_review"] = "waiting"
        active_node = "milestone_review"
    elif run_status == "AWAITING_FINAL_FEEDBACK":
        active_node = "final_present"
    elif run_status not in {"COMPLETED", "FAILED", "BLOCKED", "idle", None}:
        for nid in PATH_A_ORDER:
            if states.get(nid) == "pending":
                states[nid] = "active"
                active_node = nid
                break

    if run_status == "COMPLETED":
        for nid in PATH_A_ORDER:
            states[nid] = "done"
        states["learner"] = "done"

    if run_status in {"FAILED", "BLOCKED"}:
        for nid in PATH_A_ORDER:
            if states.get(nid) == "active":
                states[nid] = "failed"

    nodes_out = []
    for meta in ARCHITECTURE_GRAPH["nodes"]:
        nid = meta["id"]
        path = meta.get("path", "A")
        status = states.get(nid, "pending")
        if path == "B" and active_path == "A" and status == "pending":
            status = "idle"  # alternate path dimmed
        nodes_out.append({**meta, "status": status})

    return {
        "graph": ARCHITECTURE_GRAPH,
        "nodes": nodes_out,
        "edges": ARCHITECTURE_GRAPH["edges"],
        "timeline": timeline,
        "active_node": active_node,
        "active_path": active_path,
        "run_status": run_status,
        "waiting_review": waiting_review,
        "node_details": node_details,
        "run_error": run_error,
    }


def _mark_done_graph(states: dict[str, str], node_id: str, order: list[str]) -> None:
    if node_id not in order:
        states[node_id] = "done"
        return
    idx = order.index(node_id)
    for i in range(0, idx + 1):
        nid = order[i]
        if states.get(nid) not in {"failed", "waiting"}:
            states[nid] = "done"


def default_graph_progress() -> dict[str, Any]:
    return build_graph_progress([], run_status="idle", active_path="A")
