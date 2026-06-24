"""Minimal Week 1 validation."""

from __future__ import annotations

from pahs.graph.state import PAHSState


def verify_basic_node(state: PAHSState) -> dict:
    output = state.get("milestone_output", "").strip()
    if not output:
        return {
            "validation_passed": False,
            "validation_message": "Output is empty.",
        }
    if len(output) < 20:
        return {
            "validation_passed": False,
            "validation_message": "Output is too short.",
        }
    return {
        "validation_passed": True,
        "validation_message": "Basic validation passed.",
    }
