"""Mock LLM provider for Week 1 — no API keys required."""

from __future__ import annotations


def mock_triage(command: str) -> dict:
    lowered = command.lower()
    score = 25
    needs_research = any(word in lowered for word in ("research", "调研", "search", "investigate"))
    needs_code = any(word in lowered for word in ("code", "python", "file", "代码", "文件"))
    if needs_research:
        score += 25
    if needs_code:
        score += 20
    if len(command) > 120:
        score += 15

    if score < 40:
        band = "simple"
    elif score < 70:
        band = "medium"
    else:
        band = "complex"

    profile = "full" if score >= 40 else "lite"
    return {
        "complexity_score": score,
        "complexity_band": band,
        "task_type": "research_report" if needs_research else "social_post",
        "risk_level": "low",
        "needs_research": needs_research,
        "needs_code": needs_code,
        "needs_deep_reasoning": score >= 70,
        "recommended_orchestrator": profile,
        "estimated_milestones": 1 if profile == "lite" else 2,
    }


def mock_plan(command: str, profile: str, triage: dict) -> dict:
    milestone_title = "Final draft" if profile == "lite" else "Draft output"
    return {
        "intent": command,
        "orchestrator_profile": profile,
        "milestones": [
            {
                "id": "m1_output",
                "title": milestone_title,
                "deliverable_type": "text",
            }
        ],
        "estimated_cost_usd": 0.01 if profile == "lite" else 0.03,
        "triage": triage,
    }


def mock_creator_output(command: str) -> str:
    return (
        "[Mock Creator Output]\n"
        f"Task: {command}\n"
        "This is a Week 1 placeholder response. "
        "Replace with real LLM output in a later step."
    )
