"""Token and cost budget tracking for a single run."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pahs.config_loader import budget_config


@dataclass
class BudgetSnapshot:
    run_id: str
    tokens_used: int = 0
    cost_usd: float = 0.0
    daily_tokens_used: int = 0
    daily_cost_usd: float = 0.0
    alerts: list[str] = field(default_factory=list)
    proceed: bool = True
    message: str = "Budget check passed."


class BudgetManager:
    """Track per-run and daily budget using config/budget.yaml."""

    _daily_tokens: int = 0
    _daily_cost: float = 0.0

    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.config = budget_config()
        self.run_tokens = 0
        self.run_cost = 0.0

    def estimate_step(self, *, tokens: int = 500, cost_usd: float = 0.001) -> BudgetSnapshot:
        return self.check_before_step(additional_tokens=tokens, additional_cost=cost_usd)

    def check_before_step(
        self,
        *,
        additional_tokens: int,
        additional_cost: float,
    ) -> BudgetSnapshot:
        budget = self.config.get("budget", {})
        daily = budget.get("daily", {})
        per_run = budget.get("per_run", {})

        projected_run_tokens = self.run_tokens + additional_tokens
        projected_run_cost = self.run_cost + additional_cost
        projected_daily_tokens = self._daily_tokens + additional_tokens
        projected_daily_cost = self._daily_cost + additional_cost

        alerts: list[str] = []
        proceed = True
        message = "Budget check passed."

        run_token_limit = int(per_run.get("token_limit", 12000))
        run_cost_limit = float(per_run.get("cost_limit_usd", 0.10))
        run_alert = float(per_run.get("alert_threshold", 0.70))

        if projected_run_tokens > run_token_limit * run_alert:
            alerts.append("run_token_alert")
        if projected_run_cost > run_cost_limit * run_alert:
            alerts.append("run_cost_alert")

        if projected_run_tokens > run_token_limit or projected_run_cost > run_cost_limit:
            proceed = False
            message = "Run budget hard limit reached."

        daily_token_limit = int(daily.get("token_limit", 80000))
        daily_cost_limit = float(daily.get("cost_limit_usd", 0.80))
        if projected_daily_tokens > daily_token_limit or projected_daily_cost > daily_cost_limit:
            proceed = False
            message = "Daily budget hard limit reached."

        return BudgetSnapshot(
            run_id=self.run_id,
            tokens_used=projected_run_tokens,
            cost_usd=projected_run_cost,
            daily_tokens_used=projected_daily_tokens,
            daily_cost_usd=projected_daily_cost,
            alerts=alerts,
            proceed=proceed,
            message=message,
        )

    def record_step(self, *, tokens: int, cost_usd: float) -> None:
        self.run_tokens += tokens
        self.run_cost += cost_usd
        BudgetManager._daily_tokens += tokens
        BudgetManager._daily_cost += cost_usd

    @classmethod
    def reset_daily(cls) -> None:
        cls._daily_tokens = 0
        cls._daily_cost = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "tokens_used": self.run_tokens,
            "cost_usd": self.run_cost,
            "daily_tokens_used": self._daily_tokens,
            "daily_cost_usd": self._daily_cost,
        }
