"""Headless batch runs for Dev Lab stress testing and defect reports."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager, nullcontext
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import yaml

from pahs.gateway.run_ids import new_run_id
from pahs.graph.checkpoints import clear_checkpoints
from pahs.graph.runner import reset_graph_cache, resume_run, start_run
from pahs.harness.budget import BudgetManager
from pahs.paths import PROJECT_ROOT
from pahs.storage import db

SCENARIOS_PATH = PROJECT_ROOT / "config" / "dev_batch_scenarios.yaml"
MAX_RESUME_LOOPS = 12


@dataclass
class RunSummary:
    run_id: str
    scenario_id: str
    command: str
    category: str
    status: str
    worker: str | None = None
    task_type: str | None = None
    capability_gaps: list[dict[str, Any]] = field(default_factory=list)
    validation_failed: bool = False
    validation_message: str | None = None
    plan_valid: bool | None = None
    plan_warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    learner_proposals: list[str] = field(default_factory=list)
    final_feedback: str = ""
    defects: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "scenario_id": self.scenario_id,
            "command": self.command,
            "category": self.category,
            "status": self.status,
            "worker": self.worker,
            "task_type": self.task_type,
            "capability_gaps": self.capability_gaps,
            "validation_failed": self.validation_failed,
            "validation_message": self.validation_message,
            "plan_valid": self.plan_valid,
            "plan_warnings": self.plan_warnings,
            "errors": self.errors,
            "learner_proposals": self.learner_proposals,
            "final_feedback": self.final_feedback,
            "defects": self.defects,
        }


@dataclass
class BatchResult:
    started_at: str
    finished_at: str
    total_runs: int
    mock_llm: bool
    with_learner: bool
    summaries: list[RunSummary] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "total_runs": self.total_runs,
            "mock_llm": self.mock_llm,
            "with_learner": self.with_learner,
            "summaries": [item.to_dict() for item in self.summaries],
        }


def load_scenarios(path: Path | None = None) -> list[dict[str, Any]]:
    scenario_path = path or SCENARIOS_PATH
    raw = yaml.safe_load(scenario_path.read_text(encoding="utf-8")) or {}
    scenarios = raw.get("scenarios") or []
    if not scenarios:
        raise ValueError(f"No scenarios found in {scenario_path}")
    return list(scenarios)


def expand_scenarios(scenarios: list[dict[str, Any]], runs: int) -> list[dict[str, Any]]:
    if runs < 1:
        raise ValueError("runs must be >= 1")
    expanded: list[dict[str, Any]] = []
    index = 0
    while len(expanded) < runs:
        expanded.append(scenarios[index % len(scenarios)])
        index += 1
    return expanded


@contextmanager
def dev_batch_mode(*, mock_llm: bool) -> Iterator[None]:
    import os

    import pahs.providers.router as router

    prior_batch = os.environ.get("PAHS_DEV_BATCH")
    os.environ["PAHS_DEV_BATCH"] = "1"
    original_provider = None
    if mock_llm:
        original_provider = router.active_provider_name
        router.active_provider_name = lambda: "mock"  # type: ignore[method-assign]
    try:
        yield
    finally:
        if original_provider is not None:
            router.active_provider_name = original_provider  # type: ignore[method-assign]
        if prior_batch is None:
            os.environ.pop("PAHS_DEV_BATCH", None)
        else:
            os.environ["PAHS_DEV_BATCH"] = prior_batch


@contextmanager
def force_mock_llm() -> Iterator[None]:
    with dev_batch_mode(mock_llm=True):
        yield


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def collect_run_summary(
    run_id: str,
    scenario: dict[str, Any],
    *,
    final_feedback: str = "",
) -> RunSummary:
    row = db.get_run(run_id) or {}
    events = db.list_run_events(run_id)
    summary = RunSummary(
        run_id=run_id,
        scenario_id=str(scenario.get("id") or "unknown"),
        command=str(scenario.get("command") or row.get("command") or ""),
        category=str(scenario.get("category") or "general"),
        status=str(row.get("status") or "UNKNOWN"),
        final_feedback=final_feedback,
    )

    for event in events:
        event_type = str(event.get("event_type") or "")
        payload = event.get("payload") or {}
        if event_type == "triage_routing":
            summary.worker = payload.get("worker") or summary.worker
            summary.task_type = payload.get("task_type") or summary.task_type
        elif event_type == "capability_assessed":
            gaps = payload.get("gaps") or payload.get("capability_gaps") or []
            if isinstance(gaps, list):
                summary.capability_gaps = gaps
        elif event_type == "validation_failed":
            summary.validation_failed = True
            summary.validation_message = str(payload.get("message") or "Validation failed")
        elif event_type == "plan_validated":
            summary.plan_valid = payload.get("valid")
            warnings = payload.get("warnings") or []
            if isinstance(warnings, list):
                summary.plan_warnings = [str(item) for item in warnings]
        elif event_type in {"devlab_run_failed", "run_failed"}:
            summary.errors.append(str(payload.get("error") or event_type))
        elif event_type == "learner_proposals_created":
            proposal_ids = payload.get("proposal_ids") or []
            if isinstance(proposal_ids, list):
                summary.learner_proposals = [str(item) for item in proposal_ids]

    summary.defects = infer_defects(summary)
    return summary


def infer_defects(summary: RunSummary) -> list[str]:
    defects: list[str] = []
    if summary.status == "FAILED":
        defects.append(f"run_failed: {'; '.join(summary.errors) or 'unknown error'}")
    if summary.status == "BLOCKED":
        defects.append("run_blocked: budget or environment precheck blocked execution")
    if summary.validation_failed:
        defects.append(f"validation_failed: {summary.validation_message or 'no message'}")
    if summary.plan_valid is False:
        defects.append("plan_invalid: orchestrator plan did not pass validation")
    if summary.plan_warnings:
        defects.append(f"plan_warnings: {' | '.join(summary.plan_warnings[:3])}")
    if summary.capability_gaps:
        gap_ids = [
            str(item.get("code") or item.get("id") or item.get("gap_id") or item)
            if isinstance(item, dict)
            else str(item)
            for item in summary.capability_gaps
        ]
        if summary.category != "capability_gap":
            defects.append(f"capability_gaps: {', '.join(gap_ids)}")
    if summary.category == "capability_gap" and not summary.capability_gaps:
        defects.append("missing_capability_warning: account/publish task without capability gap flag")
    if summary.status in {"AWAITING_REVIEW", "AWAITING_FINAL_FEEDBACK", "ACTIVE"}:
        defects.append(f"incomplete_run: stuck at {summary.status}")
    return defects


def build_synthetic_feedback(summary: RunSummary) -> str:
    """Template feedback so Learner can draft proposals from batch defects."""
    parts: list[str] = []
    if summary.status == "FAILED":
        parts.append(f"run failed — {summary.errors[0] if summary.errors else 'unknown'}")
    if summary.validation_failed:
        parts.append("validation failed; improve output quality and cite sources")
    if summary.plan_valid is False:
        parts.append("计划步骤多余或顺序不对，应该精简流程")
    if summary.capability_gaps:
        parts.append("计划应先说明能力边界，对账号类任务给清单而非承诺代操作")
    if summary.category == "searcher" and summary.validation_failed:
        parts.append("research output needs better source citations")
    if summary.category == "creator" and summary.validation_failed:
        parts.append("creator draft too generic; should reference PAHS capabilities")
    if not parts:
        return "automated batch smoke test passed; output acceptable"
    return " | ".join(parts)


def auto_complete_run(
    run_id: str,
    scenario: dict[str, Any],
    *,
    with_learner: bool = True,
    channel: str = "dev-batch",
) -> RunSummary:
    final_feedback = ""

    for _ in range(MAX_RESUME_LOOPS):
        pending = [item for item in db.list_pending_reviews() if item["run_id"] == run_id]
        if not pending:
            break

        review_type = str(pending[-1]["review_type"])
        if review_type == "milestone_review":
            resume_run(run_id, "approved", channel=channel)
            continue

        if review_type == "final_feedback":
            partial = collect_run_summary(run_id, scenario)
            if with_learner:
                final_feedback = build_synthetic_feedback(partial)
                resume_run(run_id, final_feedback, channel=channel)
            else:
                final_feedback = "skipped"
                resume_run(run_id, "automated batch skip learner", channel=channel)
            break

        break

    return collect_run_summary(run_id, scenario, final_feedback=final_feedback)


def run_single_scenario(
    scenario: dict[str, Any],
    *,
    with_learner: bool = True,
    channel: str = "dev-batch",
) -> RunSummary:
    run_id = new_run_id()
    command = str(scenario.get("command") or "").strip()
    if not command:
        raise ValueError(f"Scenario {scenario.get('id')} has empty command")

    if channel == "dev-batch":
        # Each batch iteration should be independent; don't let daily budget accumulate.
        BudgetManager.reset_daily()

    start_run(run_id, command, channel=channel)
    return auto_complete_run(
        run_id,
        scenario,
        with_learner=with_learner,
        channel=channel,
    )


def run_batch(
    *,
    runs: int = 100,
    mock_llm: bool = True,
    with_learner: bool = True,
    scenario_file: Path | None = None,
    on_progress: Any | None = None,
    on_start: Any | None = None,
) -> BatchResult:
    db.init_db()
    scenarios = load_scenarios(scenario_file)
    plan = expand_scenarios(scenarios, runs)
    started_at = _utc_now()
    summaries: list[RunSummary] = []

    clear_checkpoints()
    reset_graph_cache()

    ctx = dev_batch_mode(mock_llm=mock_llm)
    with ctx:
        BudgetManager.reset_daily()
        for index, scenario in enumerate(plan, start=1):
            if on_start:
                on_start(index, runs, scenario)
            summary = run_single_scenario(scenario, with_learner=with_learner)
            summaries.append(summary)
            if on_progress:
                on_progress(index, runs, summary)
            if index % 25 == 0:
                clear_checkpoints()
                reset_graph_cache()

    return BatchResult(
        started_at=started_at,
        finished_at=_utc_now(),
        total_runs=runs,
        mock_llm=mock_llm,
        with_learner=with_learner,
        summaries=summaries,
    )


def save_batch_json(result: BatchResult, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path
