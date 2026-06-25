"""Orchestrator planner — builds the internal ExecutionPlan task table."""

from __future__ import annotations

import json
from typing import Any

from pahs.planning.capability_catalog import build_capability_catalog, format_catalog_for_prompt
from pahs.planning.plan_patterns import format_patterns_for_prompt, load_plan_patterns
from pahs.planning.schema import ExecutionPlan, PlanPhase, PlanTask, normalize_complexity_band, normalize_orchestrator_profile
from pahs.providers.router import active_provider_name, llm_complete


def _default_tool(worker: str, execution_mode: str | None, external_agent: str | None) -> str | None:
    if worker == "searcher":
        return "search_web"
    if worker == "creator":
        return "generate_content"
    if worker == "external":
        return external_agent
    if worker == "executor":
        return "run_python" if execution_mode == "CODE" else None
    return None


def plan_fallback_from_context(
    command: str,
    *,
    worker: str = "creator",
    execution_mode: str | None = None,
    external_agent: str = "",
    complexity_band: str = "medium",
    orchestrator_profile: str = "lite",
    task_type: str = "general_task",
) -> ExecutionPlan:
    """Single-phase fallback when LLM planning is unavailable or invalid."""
    external_name = external_agent or (execution_mode if worker == "external" else None)
    task = PlanTask(
        id="t1",
        worker=worker,  # type: ignore[arg-type]
        goal=command,
        tool=_default_tool(worker, execution_mode, external_name),
        execution_mode=execution_mode if worker == "executor" else None,
        external_agent=external_name if worker == "external" else None,
    )
    return ExecutionPlan(
        intent_summary=command[:240],
        complexity_band=normalize_complexity_band(complexity_band),  # type: ignore[arg-type]
        orchestrator_profile=normalize_orchestrator_profile(orchestrator_profile),  # type: ignore[arg-type]
        task_type=task_type,
        review_policy={"milestone_reviews": "per_phase"},
        phases=[PlanPhase(id="phase_1", title="Execute", parallel=False, tasks=[task])],
        source="fallback",
    )


def _normalize_plan_payload(payload: dict[str, Any]) -> None:
    payload["complexity_band"] = normalize_complexity_band(
        str(payload.get("complexity_band", "medium"))
    )
    payload["orchestrator_profile"] = normalize_orchestrator_profile(
        str(payload.get("orchestrator_profile", "lite"))
    )


def _parse_plan_json(raw: str, command: str) -> ExecutionPlan:
    start = raw.find("{")
    end = raw.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("No JSON object in planner response")
    payload = json.loads(raw[start : end + 1])
    if "phases" not in payload:
        raise ValueError("Planner JSON missing phases")
    payload.setdefault("intent_summary", command[:240])
    _normalize_plan_payload(payload)
    return ExecutionPlan.model_validate(payload)


def plan_with_llm(
    command: str,
    *,
    routing_context: dict[str, Any] | None = None,
    triage_result: dict[str, Any] | None = None,
    run_id: str | None = None,
) -> ExecutionPlan:
    """LLM orchestrator: produce a multi-phase ExecutionPlan (stored internally)."""
    catalog = build_capability_catalog()
    patterns = load_plan_patterns()
    ctx = routing_context or {}
    triage = triage_result or {}

    system = (
        "You are PAHS Orchestrator. Build an internal ExecutionPlan JSON only.\n"
        "Do NOT explain to the user. Return JSON with keys:\n"
        "intent_summary, complexity_band (simple|medium|complex), "
        "orchestrator_profile (lite|full), task_type, review_policy, phases.\n"
        "Each phase: id, title, parallel (bool), depends_on (phase ids), tasks.\n"
        "Each task: id, worker (searcher|creator|executor|external), goal, tool, "
        "inputs (object), inputs_from (task ids), execution_mode, external_agent.\n"
        "Use parallel=true when tasks in a phase can run together.\n"
        "Use depends_on when a phase needs outputs from earlier phases.\n"
        "Only assign capabilities from the catalog. Prefer minimal steps."
    )
    user = (
        f"User command:\n{command}\n\n"
        f"{format_catalog_for_prompt(catalog)}\n\n"
        f"{format_patterns_for_prompt(patterns)}\n\n"
        f"Triage context:\n{json.dumps(triage, ensure_ascii=False)}\n\n"
        f"Routing context:\n{json.dumps(ctx, ensure_ascii=False)}"
    )

    if active_provider_name() != "deepseek":
        raise RuntimeError("LLM planner requires DeepSeek provider")

    raw = llm_complete(
        system=system,
        user=user,
        run_id=run_id,
        phase="orchestrator_plan",
    )
    return _parse_plan_json(raw, command)


def build_execution_plan(
    command: str,
    *,
    routing_context: dict[str, Any] | None = None,
    triage_result: dict[str, Any] | None = None,
    worker: str = "creator",
    execution_mode: str | None = None,
    external_agent: str = "",
    complexity_band: str = "medium",
    orchestrator_profile: str = "lite",
    task_type: str = "general_task",
    run_id: str | None = None,
    prefer_llm: bool = True,
) -> ExecutionPlan:
    """Create an ExecutionPlan via LLM, falling back to a single-task plan."""
    if prefer_llm:
        try:
            plan = plan_with_llm(
                command,
                routing_context=routing_context,
                triage_result=triage_result,
                run_id=run_id,
            )
            plan.source = "orchestrator_llm"
            return plan
        except Exception:
            pass

    return plan_fallback_from_context(
        command,
        worker=worker,
        execution_mode=execution_mode,
        external_agent=external_agent,
        complexity_band=complexity_band,
        orchestrator_profile=orchestrator_profile,
        task_type=task_type,
    )
