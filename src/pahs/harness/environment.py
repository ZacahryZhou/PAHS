"""Environment checks before execution steps."""

from __future__ import annotations

from typing import Any

from pahs.harness.budget import BudgetManager
from pahs.graph.state import PAHSState
from pahs.routing.cost_estimator import estimate_run_cost, record_cost_event
from pahs.routing.llm_router import route_model


class EnvironmentMonitor:
    """Combine budget checks with lightweight environment validation."""

    def __init__(self, budget: BudgetManager) -> None:
        self.budget = budget

    def precheck(self, state: PAHSState, *, step_name: str) -> dict[str, Any]:
        cost_estimate = dict(state.get("cost_estimate") or {})
        routing_context = state.get("routing_context") or {}
        routing_decision = dict(state.get("routing_decision") or {})

        estimated_tokens = int(cost_estimate.get("estimated_tokens", 800))
        estimated_cost = float(cost_estimate.get("estimated_cost_usd", 0.01))

        snapshot = self.budget.check_before_step(
            additional_tokens=estimated_tokens,
            additional_cost=estimated_cost,
        )

        downgraded = False
        if snapshot.alerts and snapshot.proceed:
            routing_decision = route_model(routing_context, budget_alerts=snapshot.alerts)
            cost_estimate = estimate_run_cost(routing_context, routing_decision)
            estimated_tokens = int(cost_estimate.get("estimated_tokens", estimated_tokens))
            estimated_cost = float(cost_estimate.get("estimated_cost_usd", estimated_cost))
            downgraded = True

        if snapshot.proceed:
            self.budget.record_step(tokens=estimated_tokens, cost_usd=estimated_cost)

        return {
            "budget_snapshot": snapshot.__dict__,
            "env_check_passed": snapshot.proceed,
            "env_check_message": snapshot.message,
            "routing_decision": routing_decision,
            "cost_estimate": cost_estimate,
            "harness_event": {
                "type": "environment_precheck",
                "step": step_name,
                "alerts": snapshot.alerts,
                "proceed": snapshot.proceed,
                "downgraded": downgraded,
                "selected_model": routing_decision.get("selected_model"),
            },
        }
