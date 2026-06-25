"""Holistic Learner analysis after a dev-batch run."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pahs.devlab.batch_report import build_recommendations, _group_defects
from pahs.devlab.batch_runner import BatchResult, RunSummary
from pahs.gateway.run_ids import new_run_id
from pahs.learning.learner import analyze_feedback
from pahs.learning.proposals import Proposal, create_proposal
from pahs.paths import ensure_data_dir
from pahs.storage import db


@dataclass
class CodeAction:
    priority: str
    title: str
    files: list[str]
    description: str
    acceptance: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "priority": self.priority,
            "title": self.title,
            "files": self.files,
            "description": self.description,
            "acceptance": self.acceptance,
        }


@dataclass
class BatchImprovementPlan:
    batch_id: str
    batch_feedback: str
    findings: list[dict[str, Any]] = field(default_factory=list)
    code_actions: list[CodeAction] = field(default_factory=list)
    rule_proposals: list[Proposal] = field(default_factory=list)
    per_run_proposal_ids: list[str] = field(default_factory=list)
    cursor_handoff: str = ""
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "batch_feedback": self.batch_feedback,
            "findings": self.findings,
            "code_actions": [item.to_dict() for item in self.code_actions],
            "rule_proposal_ids": [item.proposal_id for item in self.rule_proposals],
            "per_run_proposal_ids": self.per_run_proposal_ids,
            "cursor_handoff": self.cursor_handoff,
            "stats": self.stats,
        }


def actionable_defects(summary: RunSummary) -> list[str]:
    """Defects that need fixing — exclude expected capability warnings on gap scenarios."""
    defects = list(summary.defects)
    if summary.category == "capability_gap" and summary.capability_gaps:
        defects = [item for item in defects if not item.startswith("capability_gaps:")]
    return defects


def build_batch_payload(result: BatchResult) -> dict[str, Any]:
    summaries = result.summaries
    all_proposal_ids: list[str] = []
    for summary in summaries:
        all_proposal_ids.extend(summary.learner_proposals)

    actionable_runs = [item for item in summaries if actionable_defects(item)]
    defect_groups = _group_defects(
        [RunSummary(**{**item.to_dict(), "defects": actionable_defects(item)}) for item in summaries]
    )

    return {
        "total_runs": result.total_runs,
        "mock_llm": result.mock_llm,
        "completed": sum(1 for item in summaries if item.status == "COMPLETED"),
        "failed": sum(1 for item in summaries if item.status == "FAILED"),
        "actionable_runs": len(actionable_runs),
        "defect_groups": [
            {"key": key, "count": count, "examples": examples}
            for key, count, examples in defect_groups
        ],
        "scenario_stats": _scenario_stats(summaries),
        "worker_stats": dict(Counter(item.worker or "unknown" for item in summaries)),
        "summaries": [item.to_dict() for item in summaries],
        "per_run_proposal_ids": sorted(set(all_proposal_ids)),
    }


def _scenario_stats(summaries: list[RunSummary]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for summary in summaries:
        bucket = by_id.setdefault(
            summary.scenario_id,
            {
                "scenario_id": summary.scenario_id,
                "category": summary.category,
                "runs": 0,
                "actionable": 0,
                "commands": set(),
            },
        )
        bucket["runs"] += 1
        bucket["commands"].add(summary.command)
        if actionable_defects(summary):
            bucket["actionable"] += 1
    rows = []
    for item in by_id.values():
        rows.append(
            {
                "scenario_id": item["scenario_id"],
                "category": item["category"],
                "runs": item["runs"],
                "actionable": item["actionable"],
                "commands": sorted(item["commands"]),
            }
        )
    return sorted(rows, key=lambda row: (-row["actionable"], row["scenario_id"]))


def synthesize_batch_feedback(result: BatchResult, payload: dict[str, Any]) -> str:
    parts: list[str] = []
    for group in payload["defect_groups"][:8]:
        key = group["key"]
        count = group["count"]
        examples = ", ".join(group["examples"][:2])
        parts.append(f"[{key}] appeared {count}x (e.g. {examples})")

    for rec in build_recommendations(result)[:6]:
        parts.append(rec)

    scenario_hot = [
        row
        for row in payload["scenario_stats"]
        if row["actionable"] > 0
    ][:5]
    for row in scenario_hot:
        parts.append(
            f"scenario {row['scenario_id']} had {row['actionable']}/{row['runs']} actionable issues"
        )

    if not parts:
        return (
            "Batch smoke test passed across scenarios. "
            "Keep monitoring routing, validation, and capability boundaries."
        )
    return " | ".join(parts)


def plan_code_actions(result: BatchResult, payload: dict[str, Any]) -> list[CodeAction]:
    actions: list[CodeAction] = []
    defect_keys = Counter(group["key"] for group in payload["defect_groups"])

    if defect_keys.get("run_failed", 0):
        actions.append(
            CodeAction(
                priority="P0",
                title="Fix LangGraph run failures",
                files=["src/pahs/graph/", "src/pahs/devlab/batch_runner.py"],
                description="Batch runs failed before completion. Trace failing run_ids and fix the graph node or resume loop.",
                acceptance="Re-run dev-batch; run_failed count is 0.",
            )
        )
    if defect_keys.get("incomplete_run", 0):
        actions.append(
            CodeAction(
                priority="P0",
                title="Fix batch auto-resume interrupts",
                files=["src/pahs/devlab/batch_runner.py", "src/pahs/graph/runner.py"],
                description="Runs stuck at AWAITING_REVIEW or AWAITING_FINAL_FEEDBACK during dev-batch.",
                acceptance="All batch runs reach COMPLETED without manual input.",
            )
        )
    if defect_keys.get("validation_failed", 0):
        actions.append(
            CodeAction(
                priority="P1",
                title="Improve output validation and agent prompts",
                files=[
                    "src/pahs/agents/week1.py",
                    "src/pahs/agents/searcher.py",
                    "src/pahs/harness/validation.py",
                ],
                description="Validation failed on creator/searcher deliverables during batch.",
                acceptance="validation_failed defects drop on affected scenarios.",
            )
        )
    if defect_keys.get("plan_invalid", 0) or defect_keys.get("plan_warnings", 0):
        actions.append(
            CodeAction(
                priority="P1",
                title="Stabilize orchestrator plans",
                files=[
                    "src/pahs/planning/orchestrator_planner.py",
                    "src/pahs/planning/schema.py",
                    "src/pahs/planning/validation.py",
                ],
                description="Plans failed validation or produced warnings too often in batch.",
                acceptance="plan_invalid and plan_warnings counts decrease.",
            )
        )
    if defect_keys.get("missing_capability_warning", 0):
        actions.append(
            CodeAction(
                priority="P1",
                title="Expand capability gap detection",
                files=["src/pahs/harness/capability_brief.py"],
                description="Account/publish/payment commands did not trigger capability_assessed gaps.",
                acceptance="capability_gap scenarios always emit gaps; missing_capability_warning is 0.",
            )
        )
    if defect_keys.get("capability_gaps", 0):
        actions.append(
            CodeAction(
                priority="P2",
                title="Surface capability boundaries earlier in UX",
                files=[
                    "src/pahs/devlab/static/index.html",
                    "src/pahs/planning/orchestrator_planner.py",
                    "src/pahs/planning/task_context.py",
                ],
                description="Capability gaps were detected but plans/UI should state limits in the first response.",
                acceptance="Orchestrator plans and Dev Lab banner clearly list alternatives for gap tasks.",
            )
        )

    if not actions and payload["actionable_runs"] == 0:
        actions.append(
            CodeAction(
                priority="P3",
                title="No urgent code changes",
                files=[],
                description="Batch passed without actionable defects. Consider scaling to --runs 100 and testing with --no-mock.",
                acceptance="Optional follow-up batch at higher volume.",
            )
        )
    return actions


def _dedupe_drafts(drafts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    unique: list[dict[str, Any]] = []
    for draft in drafts:
        key = (str(draft.get("target_path") or ""), str(draft.get("title") or ""))
        if key in seen:
            continue
        seen.add(key)
        unique.append(draft)
    return unique


def learn_from_batch(result: BatchResult) -> BatchImprovementPlan:
    db.init_db()
    batch_id = new_run_id().replace("run_", "batch_", 1)
    db.create_run(
        batch_id,
        f"dev-batch analysis ({result.total_runs} runs)",
        channel="dev-batch",
        status="BATCH",
    )

    payload = build_batch_payload(result)
    batch_feedback = synthesize_batch_feedback(result, payload)
    code_actions = plan_code_actions(result, payload)

    context = {
        "task_type": "batch_analysis",
        "worker": "orchestrator",
        "execution_plan": {
            "intent_summary": f"Aggregate analysis of {result.total_runs} dev-batch runs",
            "phases": payload["defect_groups"],
        },
    }
    drafts = analyze_feedback(batch_feedback, run_context=context)
    drafts = _dedupe_drafts(drafts)

    findings = []
    for group in payload["defect_groups"]:
        findings.append(
            {
                "type": group["key"],
                "count": group["count"],
                "examples": group["examples"],
                "severity": "high" if group["key"] in {"run_failed", "incomplete_run", "missing_capability_warning"} else "medium",
            }
        )

    rule_proposals: list[Proposal] = []
    for draft in drafts:
        proposal = create_proposal(
            run_id=batch_id,
            feedback_text=batch_feedback,
            proposal_type=draft["proposal_type"],
            target_path=draft["target_path"],
            title=f"[Batch] {draft['title']}",
            proposed_content=draft["proposed_content"],
            rationale=draft["rationale"],
        )
        rule_proposals.append(proposal)

    db.log_event(
        batch_id,
        "batch_learner_analysis",
        {
            "batch_feedback": batch_feedback,
            "stats": {
                "total_runs": payload["total_runs"],
                "actionable_runs": payload["actionable_runs"],
                "code_action_count": len(code_actions),
                "rule_proposal_count": len(rule_proposals),
            },
            "defect_groups": payload["defect_groups"],
            "code_actions": [item.to_dict() for item in code_actions],
            "rule_proposal_ids": [item.proposal_id for item in rule_proposals],
            "per_run_proposal_ids": payload["per_run_proposal_ids"],
        },
    )

    plan = BatchImprovementPlan(
        batch_id=batch_id,
        batch_feedback=batch_feedback,
        findings=findings,
        code_actions=code_actions,
        rule_proposals=rule_proposals,
        per_run_proposal_ids=payload["per_run_proposal_ids"],
        stats=payload,
    )
    plan.cursor_handoff = build_cursor_handoff(plan, result)
    return plan


def build_cursor_handoff(plan: BatchImprovementPlan, result: BatchResult) -> str:
    lines = [
        "PAHS batch improvement handoff for Cursor agent",
        f"batch_id={plan.batch_id}",
        f"runs={result.total_runs}, actionable={plan.stats.get('actionable_runs', 0)}",
        "",
        "Learner batch feedback:",
        plan.batch_feedback,
        "",
        "Code actions (implement in src/pahs/):",
    ]
    for action in plan.code_actions:
        files = ", ".join(action.files) if action.files else "n/a"
        lines.append(f"- [{action.priority}] {action.title}")
        lines.append(f"  files: {files}")
        lines.append(f"  do: {action.description}")
        lines.append(f"  done when: {action.acceptance}")
    lines.append("")
    lines.append("Rule proposals (user approves via pah proposals approve):")
    for proposal in plan.rule_proposals[:10]:
        lines.append(f"- {proposal.proposal_id}: {proposal.title}")
    lines.append("")
    lines.append("Please implement code actions by priority. Do not auto-approve rule proposals.")
    return "\n".join(lines)


def render_improvement_plan(plan: BatchImprovementPlan, result: BatchResult) -> str:
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# PAHS Batch Improvement Plan | 批量测试改进方案",
        "",
        f"- Generated | 生成时间: {generated}",
        f"- Batch ID | 批次: `{plan.batch_id}`",
        f"- Runs | 运行次数: {result.total_runs}",
        f"- Actionable runs | 需处理运行: {plan.stats.get('actionable_runs', 0)}",
        "",
        "---",
        "",
        "## 1. Learner 整体分析 | Holistic Analysis",
        "",
        plan.batch_feedback,
        "",
    ]

    if plan.findings:
        lines.extend(["### 主要发现 | Key Findings", ""])
        for item in plan.findings:
            lines.append(
                f"- **{item['type']}** × {item['count']} (severity: {item['severity']}) "
                f"— e.g. {', '.join(item['examples'][:2])}"
            )
        lines.append("")

    lines.extend(
        [
            "---",
            "",
            "## 2. 规则层方案（你来 approve）| Rule Layer — You Approve",
            "",
            "这些提案已写入 `rules/learnings/pending/`，**不会自动生效**。",
            "",
        ]
    )
    if not plan.rule_proposals:
        lines.append("_本批次 Learner 未生成额外批量规则提案。_")
    else:
        for proposal in plan.rule_proposals:
            lines.append(f"### `{proposal.proposal_id}` — {proposal.title}")
            lines.append(f"- Target: `{proposal.target_path}`")
            lines.append(f"- Rationale: {proposal.rationale}")
            lines.append("")
            lines.append("```")
            lines.append(proposal.proposed_content[:1200])
            lines.append("```")
            lines.append("")
        lines.append("```bash")
        lines.append("python3 -m pahs.cli proposals pending")
        lines.append("python3 -m pahs.cli proposals approve <proposal_id>")
        lines.append("```")
        lines.append("")

    lines.extend(
        [
            "---",
            "",
            "## 3. 代码层方案（复制给 Cursor）| Code Layer — Give to Cursor",
            "",
        ]
    )
    for action in plan.code_actions:
        files = ", ".join(f"`{path}`" for path in action.files) if action.files else "_none_"
        lines.extend(
            [
                f"### [{action.priority}] {action.title}",
                f"- Files | 相关文件: {files}",
                f"- Action | 做什么: {action.description}",
                f"- Done when | 完成标准: {action.acceptance}",
                "",
            ]
        )

    if plan.per_run_proposal_ids:
        lines.extend(
            [
                "---",
                "",
                "## 4. 单次运行提案汇总 | Per-Run Proposals",
                "",
                f"共 {len(plan.per_run_proposal_ids)} 条（批量前每轮 Learner 已生成）:",
                "",
            ]
        )
        for proposal_id in plan.per_run_proposal_ids[:20]:
            row = db.get_proposal(proposal_id)
            title = row.get("title") if row else proposal_id
            lines.append(f"- `{proposal_id}` — {title}")
        if len(plan.per_run_proposal_ids) > 20:
            lines.append(f"- … and {len(plan.per_run_proposal_ids) - 20} more")
        lines.append("")

    lines.extend(
        [
            "---",
            "",
            "## 5. 复制给 Cursor | Copy-Paste Handoff",
            "",
            "```text",
            plan.cursor_handoff,
            "```",
            "",
            "## 6. 推荐工作流 | Workflow",
            "",
            "1. 把上面 **Copy-Paste Handoff** 整段贴给 Cursor → 改代码",
            "2. `pah proposals pending` → 批准有用的规则提案",
            "3. 再跑 `pah dev-batch` → 对比新报告是否变好",
            "",
        ]
    )
    return "\n".join(lines)


def default_plan_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return ensure_data_dir() / f"dev_batch_improvement_plan_{stamp}.md"


def write_improvement_plan(
    plan: BatchImprovementPlan,
    result: BatchResult,
    path: Path | None = None,
) -> Path:
    target = path or default_plan_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_improvement_plan(plan, result), encoding="utf-8")
    json_path = target.with_suffix(".json")
    json_path.write_text(
        json.dumps(
            {"plan": plan.to_dict(), "batch_result_meta": result.to_dict()},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return target


def analyze_batch_from_json(json_path: Path) -> tuple[BatchResult, BatchImprovementPlan]:
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    summaries = [RunSummary(**item) for item in raw.get("summaries", [])]
    result = BatchResult(
        started_at=str(raw.get("started_at") or ""),
        finished_at=str(raw.get("finished_at") or ""),
        total_runs=int(raw.get("total_runs") or len(summaries)),
        mock_llm=bool(raw.get("mock_llm")),
        with_learner=bool(raw.get("with_learner")),
        summaries=summaries,
    )
    plan = learn_from_batch(result)
    return result, plan
