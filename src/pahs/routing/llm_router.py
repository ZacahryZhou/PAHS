"""LLM routing with downgrade support."""

from __future__ import annotations

from typing import Any

from pahs.config_loader import load_yaml


def models_config() -> dict[str, Any]:
    return load_yaml("models.yaml")


def route_model(routing_context: dict[str, Any], *, budget_alerts: list[str] | None = None) -> dict[str, Any]:
    config = models_config()
    defaults = config.get("routing_defaults", {})
    downgrade_chain = config.get("downgrade_chain", {})
    alerts = budget_alerts or []

    worker = routing_context.get("worker", "creator")
    mode = routing_context.get("execution_mode")
    task_type = routing_context.get("task_type", "general_task")
    quality = routing_context.get("quality_required", "standard")

    if mode == "DEEP_THINK":
        role_key = "deep_think"
    elif worker == "external":
        role_key = "orchestrator_full"
    elif worker == "searcher":
        role_key = "searcher_summary"
    elif worker == "executor" and mode == "CODE":
        role_key = "code"
    elif worker == "executor" and mode == "ANALYSIS":
        role_key = "analysis"
    elif quality == "high":
        role_key = "creator_high_quality"
    else:
        profile = routing_context.get("orchestrator_profile", "lite")
        role_key = "orchestrator_lite" if profile == "lite" else "orchestrator_full"
        if worker == "creator":
            role_key = "creator"

    selected_model = defaults.get(role_key, defaults.get("creator", "deepseek-chat"))
    reason = f"default for role `{role_key}`"

    if alerts and selected_model in downgrade_chain:
        selected_model = downgrade_chain[selected_model]
        reason = f"budget alert downgrade from `{role_key}`"

    return {
        "role_key": role_key,
        "selected_model": selected_model,
        "reason": reason,
        "task_type": task_type,
        "budget_alerts": alerts,
    }
