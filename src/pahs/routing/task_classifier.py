"""Structured task classification for routing."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from pahs.providers.mock import mock_triage
from pahs.routing.worker_router import choose_worker


@dataclass
class RoutingContext:
    task_type: str
    complexity_band: str
    complexity_score: int
    orchestrator_profile: str
    worker: str
    execution_mode: str | None
    needs_research: bool
    needs_code: bool
    needs_deep_reasoning: bool
    quality_required: str
    risk_level: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _task_type_from_triage(command: str, triage: dict[str, Any], worker: str) -> str:
    if worker == "searcher":
        return "research_report"
    if worker == "executor":
        mode = triage.get("execution_mode")
        if mode == "ANALYSIS":
            return "analysis_task"
        return "code_task"
    lowered = command.lower()
    if any(word in lowered for word in ("post", "tweet", "文案", "推文")):
        return "social_post"
    return "general_task"


def classify_command(command: str) -> dict[str, Any]:
    triage = mock_triage(command)
    worker, execution_mode = choose_worker(command, triage)
    task_type = _task_type_from_triage(command, {**triage, "execution_mode": execution_mode}, worker)
    quality_required = "high" if triage.get("complexity_band") == "complex" else "standard"
    if triage.get("complexity_band") == "simple":
        quality_required = "draft"

    context = RoutingContext(
        task_type=task_type,
        complexity_band=triage["complexity_band"],
        complexity_score=int(triage["complexity_score"]),
        orchestrator_profile=triage["recommended_orchestrator"],
        worker=worker,
        execution_mode=execution_mode,
        needs_research=bool(triage.get("needs_research")),
        needs_code=bool(triage.get("needs_code")),
        needs_deep_reasoning=bool(triage.get("needs_deep_reasoning")),
        quality_required=quality_required,
        risk_level=str(triage.get("risk_level", "low")),
    )
    return {
        "triage_result": triage,
        "routing_context": context.to_dict(),
        "orchestrator_profile": context.orchestrator_profile,
        "complexity_band": context.complexity_band,
        "worker": worker,
        "execution_mode": execution_mode,
        "task_type": task_type,
    }
