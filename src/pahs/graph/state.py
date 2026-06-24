"""Shared graph state for Week 1."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class PAHSState(TypedDict, total=False):
    run_id: str
    user_command: str
    channel: str
    triage_result: dict[str, Any]
    orchestrator_profile: Literal["lite", "full"]
    plan: dict[str, Any]
    milestone_id: str
    milestone_output: str
    validation_passed: bool
    validation_message: str
    presentation: str
    user_milestone_review: str
    user_final_feedback: str
    final_response: str
    status: str
