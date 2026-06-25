"""Choose worker assignment for Week 3+ planning."""

from __future__ import annotations

from typing import Any

from pahs.external.registry import match_external_agent


def choose_worker(command: str, triage: dict[str, Any]) -> tuple[str, str | None]:
    external = match_external_agent(command)
    if external is not None:
        return "external", external.name

    lowered = command.lower()
    if triage.get("needs_research"):
        return "searcher", None
    if triage.get("needs_deep_reasoning"):
        return "executor", "DEEP_THINK"
    if any(word in lowered for word in ("csv", "data", "analysis", "chart", "metric", "数据", "分析")):
        return "executor", "ANALYSIS"
    if triage.get("needs_code"):
        return "executor", "CODE"
    return "creator", None
