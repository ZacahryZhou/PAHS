"""Estimate and compare run costs."""

from __future__ import annotations

from typing import Any

from pahs.storage import db

# Week 4 rough mock pricing for planning only.
MODEL_COST_PER_1K_TOKENS = {
    "deepseek-chat": 0.0003,
    "deepseek-reasoner": 0.0006,
    "claude-sonnet": 0.003,
    "gpt-4o": 0.005,
    "kimi-k2": 0.0004,
}


def estimate_run_cost(routing_context: dict[str, Any], routing_decision: dict[str, Any]) -> dict[str, Any]:
    band = routing_context.get("complexity_band", "simple")
    worker = routing_context.get("worker", "creator")
    model = routing_decision.get("selected_model", "deepseek-chat")

    token_map = {
        "simple": 1200,
        "medium": 2800,
        "complex": 5000,
    }
    base_tokens = token_map.get(band, 1500)
    if worker == "searcher":
        base_tokens += 800
    if routing_context.get("execution_mode") == "DEEP_THINK":
        base_tokens += 1200

    rate = MODEL_COST_PER_1K_TOKENS.get(model, 0.0003)
    estimated_cost = round((base_tokens / 1000) * rate, 6)

    return {
        "estimated_tokens": base_tokens,
        "estimated_cost_usd": estimated_cost,
        "selected_model": model,
        "worker": worker,
        "complexity_band": band,
    }


def record_cost_event(
    run_id: str,
    *,
    phase: str,
    estimated: dict[str, Any],
    actual: dict[str, Any] | None = None,
) -> None:
    payload = {
        "phase": phase,
        "estimated": estimated,
        "actual": actual or {},
    }
    if actual:
        payload["delta_cost_usd"] = round(
            float(actual.get("cost_usd", 0.0)) - float(estimated.get("estimated_cost_usd", 0.0)),
            6,
        )
    db.log_event(run_id, "cost_tracking", payload)
