"""ExecutionPlan schema — internal task table for multi-agent runs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


WorkerName = Literal["searcher", "creator", "executor", "external"]


class PlanTask(BaseModel):
    id: str
    worker: WorkerName
    goal: str
    tool: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    inputs_from: list[str] = Field(default_factory=list)
    execution_mode: str | None = None
    external_agent: str | None = None

    @field_validator("id")
    @classmethod
    def _id_not_empty(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("task id must not be empty")
        return text


class PlanPhase(BaseModel):
    id: str
    title: str
    parallel: bool = False
    depends_on: list[str] = Field(default_factory=list)
    tasks: list[PlanTask] = Field(min_length=1)

    @field_validator("id")
    @classmethod
    def _id_not_empty(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("phase id must not be empty")
        return text


_BAND_ALIASES = {
    "low": "simple",
    "high": "complex",
    "simple": "simple",
    "medium": "medium",
    "complex": "complex",
}
_PROFILE_ALIASES = {
    "simple": "lite",
    "lite": "lite",
    "full": "full",
    "research": "full",
    "deep": "full",
    "standard": "lite",
}


def normalize_complexity_band(value: str | None, *, default: str = "medium") -> str:
    return _BAND_ALIASES.get(str(value or default).lower(), default)


def normalize_orchestrator_profile(value: str | None, *, default: str = "lite") -> str:
    return _PROFILE_ALIASES.get(str(value or default).lower(), default)


class ExecutionPlan(BaseModel):
    plan_version: int = 1
    intent_summary: str
    complexity_band: Literal["simple", "medium", "complex"] = "medium"
    orchestrator_profile: Literal["lite", "full"] = "lite"
    task_type: str = "general_task"
    review_policy: dict[str, Any] = Field(
        default_factory=lambda: {"milestone_reviews": "per_phase"}
    )
    phases: list[PlanPhase] = Field(min_length=1)
    source: str = "orchestrator"

    @field_validator("complexity_band", mode="before")
    @classmethod
    def _normalize_band(cls, value: Any) -> str:
        return normalize_complexity_band(str(value) if value is not None else None)

    @field_validator("orchestrator_profile", mode="before")
    @classmethod
    def _normalize_profile(cls, value: Any) -> str:
        return normalize_orchestrator_profile(str(value) if value is not None else None)

    def phase_count(self) -> int:
        return len(self.phases)

    def task_count(self) -> int:
        return sum(len(phase.tasks) for phase in self.phases)

    def primary_worker(self) -> str:
        return self.phases[0].tasks[0].worker

    def to_storage_dict(self) -> dict[str, Any]:
        return self.model_dump()


class TaskArtifact(BaseModel):
    task_id: str
    phase_id: str
    worker: str
    goal: str
    output: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_storage_dict(self) -> dict[str, Any]:
        return self.model_dump()
