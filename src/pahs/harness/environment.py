"""Environment checks before execution steps."""

from __future__ import annotations

from typing import Any

from pahs.harness.budget import BudgetManager
from pahs.graph.state import PAHSState


class EnvironmentMonitor:
    """Combine budget checks with lightweight environment validation."""

    def __init__(self, budget: BudgetManager) -> None:
        self.budget = budget

    def precheck(self, state: PAHSState, *, step_name: str) -> dict[str, Any]:
        plan = state.get("plan") or {}
        estimated_cost = float(plan.get("estimated_cost_usd", 0.01))
        estimated_tokens = 800 if state.get("orchestrator_profile") == "lite" else 1500

        snapshot = self.budget.check_before_step(
            additional_tokens=estimated_tokens,
            additional_cost=estimated_cost,
        )

        if snapshot.proceed:
            self.budget.record_step(tokens=estimated_tokens, cost_usd=estimated_cost)

        return {
            "budget_snapshot": snapshot.__dict__,
            "env_check_passed": snapshot.proceed,
            "env_check_message": snapshot.message,
            "harness_event": {
                "type": "environment_precheck",
                "step": step_name,
                "alerts": snapshot.alerts,
                "proceed": snapshot.proceed,
            },
        }
