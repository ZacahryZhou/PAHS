"""Harness validation pipeline — Stage 1, 1.5, optional Stage 2 placeholder."""

from __future__ import annotations

from pahs.config_loader import budget_config
from pahs.graph.state import PAHSState

FORBIDDEN_SNIPPETS = ("api_key", "password", "secret")


def _stage1_rules(output: str) -> tuple[bool, str, float]:
    if not output.strip():
        return False, "Stage 1 failed: output is empty.", 0.0
    if len(output.strip()) < 20:
        return False, "Stage 1 failed: output is too short.", 0.2
    lowered = output.lower()
    for snippet in FORBIDDEN_SNIPPETS:
        if snippet in lowered:
            return False, f"Stage 1 failed: forbidden snippet `{snippet}` detected.", 0.0
    return True, "Stage 1 passed.", 0.85


def _stage1_5_heuristics(output: str, command: str) -> tuple[bool, str, float]:
    score = 0.5
    if "[mock creator output]" in output.lower():
        score += 0.2
    if any(token in command.lower() for token in command.split()[:3]):
        score += 0.15
    if len(output) >= 60:
        score += 0.1
    passed = score >= 0.6
    message = "Stage 1.5 passed." if passed else "Stage 1.5 failed: heuristic score too low."
    return passed, message, score


def _needs_stage2(score: float) -> bool:
    behavior = budget_config().get("behavior", {})
    if behavior.get("stage_2_llm_verification") != "gray_area_only":
        return True
    return 0.5 <= score < 0.9


def verify_pipeline_node(state: PAHSState) -> dict:
    output = state.get("milestone_output", "")
    command = state.get("user_command", "")
    worker = state.get("worker", state.get("active_agent", "creator"))

    if worker == "searcher":
        sources = state.get("sources", [])
        if not sources and "http" not in output:
            return {
                "validation_passed": False,
                "validation_message": "Searcher output must include sources.",
                "validation_score": 0.0,
                "validation_stage": "stage_1",
            }

    ok, message, score = _stage1_rules(output)
    if not ok:
        return {
            "validation_passed": False,
            "validation_message": message,
            "validation_score": score,
            "validation_stage": "stage_1",
        }

    ok, message, score = _stage1_5_heuristics(output, command)
    if not ok:
        return {
            "validation_passed": False,
            "validation_message": message,
            "validation_score": score,
            "validation_stage": "stage_1_5",
        }

    if _needs_stage2(score):
        # Week 2 keeps Stage 2 as a placeholder without calling an LLM.
        return {
            "validation_passed": True,
            "validation_message": "Stage 2 skipped in Week 2 mock mode; gray area accepted.",
            "validation_score": score,
            "validation_stage": "stage_2_skipped",
        }

    return {
        "validation_passed": True,
        "validation_message": "Validation pipeline passed.",
        "validation_score": score,
        "validation_stage": "stage_1_5",
    }


# Backward-compatible alias used by older imports/tests.
verify_basic_node = verify_pipeline_node
