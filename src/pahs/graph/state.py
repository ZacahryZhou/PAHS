"""Shared graph state."""

from __future__ import annotations

from typing import Any, Literal, TypedDict


class PAHSState(TypedDict, total=False):
    run_id: str
    user_command: str
    channel: str
    triage_result: dict[str, Any]
    routing_context: dict[str, Any]
    routing_decision: dict[str, Any]
    cost_estimate: dict[str, Any]
    task_type: str
    standards_loaded: list[str]
    orchestrator_profile: Literal["lite", "full"]
    complexity_band: Literal["simple", "medium", "complex"]
    review_policy: dict[str, Any]
    plan: dict[str, Any]
    milestone_id: str
    milestone_output: str
    loaded_rules: list[str]
    active_agent: str
    worker: str
    execution_mode: str | None
    external_agent: str
    external_result: dict[str, Any]
    sources: list[dict[str, Any]]
    tools_available: list[str]
    budget_snapshot: dict[str, Any]
    env_check_passed: bool
    env_check_message: str
    validation_passed: bool
    validation_message: str
    validation_score: float
    validation_stage: str
    retry_count: int
    last_validation_message: str
    last_output_fingerprint: str
    no_progress_detected: bool
    presentation: str
    user_milestone_review: str
    user_final_feedback: str
    final_response: str
    status: str
