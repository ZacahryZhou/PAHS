"""Aggregate batch run results into a copy-paste defect report."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pahs.devlab.batch_runner import BatchResult, RunSummary
from pahs.paths import ensure_data_dir
from pahs.storage import db


def _pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return "0%"
    return f"{numerator / denominator * 100:.1f}%"


def _group_defects(summaries: list[RunSummary]) -> list[tuple[str, int, list[str]]]:
    counter: Counter[str] = Counter()
    examples: dict[str, list[str]] = {}
    for summary in summaries:
        for defect in summary.defects:
            key = defect.split(":", 1)[0]
            counter[key] += 1
            examples.setdefault(key, [])
            if len(examples[key]) < 3:
                examples[key].append(f"{summary.scenario_id} ({summary.run_id})")
    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return [(key, count, examples.get(key, [])) for key, count in ranked]


def _status_counts(summaries: list[RunSummary]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for summary in summaries:
        counts[summary.status] += 1
    return dict(counts)


def _worker_counts(summaries: list[RunSummary]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for summary in summaries:
        counts[summary.worker or "unknown"] += 1
    return dict(counts)


def _collect_proposal_titles(proposal_ids: list[str]) -> list[str]:
    titles: list[str] = []
    for proposal_id in proposal_ids:
        row = db.get_proposal(proposal_id)
        if row:
            titles.append(str(row.get("title") or proposal_id))
        else:
            titles.append(proposal_id)
    return titles


def render_markdown_report(result: BatchResult) -> str:
    summaries = result.summaries
    total = len(summaries)
    completed = sum(1 for item in summaries if item.status == "COMPLETED")
    failed = sum(1 for item in summaries if item.status == "FAILED")
    blocked = sum(1 for item in summaries if item.status == "BLOCKED")
    stuck = sum(
        1
        for item in summaries
        if item.status in {"AWAITING_REVIEW", "AWAITING_FINAL_FEEDBACK", "ACTIVE"}
    )
    with_defects = sum(1 for item in summaries if item.defects)
    validation_failures = sum(1 for item in summaries if item.validation_failed)
    capability_hits = sum(1 for item in summaries if item.capability_gaps)
    proposal_runs = [item for item in summaries if item.learner_proposals]
    all_proposal_ids: list[str] = []
    for item in summaries:
        all_proposal_ids.extend(item.learner_proposals)
    unique_proposals = sorted(set(all_proposal_ids))

    status_counts = _status_counts(summaries)
    worker_counts = _worker_counts(summaries)
    defect_groups = _group_defects(summaries)

    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        "# PAHS Dev Batch Report | 批量测试报告",
        "",
        f"- Generated | 生成时间: {generated}",
        f"- Runs | 运行次数: {result.total_runs}",
        f"- Mock LLM | 模拟模型: {'yes' if result.mock_llm else 'no'}",
        f"- Learner feedback | Learner 反馈: {'yes' if result.with_learner else 'no'}",
        f"- Window | 时间窗: {result.started_at} → {result.finished_at}",
        "",
        "## Executive Summary | 摘要",
        "",
        f"- Completed | 完成: **{completed}/{total}** ({_pct(completed, total)})",
        f"- Failed | 失败: **{failed}/{total}** ({_pct(failed, total)})",
        f"- Blocked | 预算/环境阻断: **{blocked}/{total}** ({_pct(blocked, total)})",
        f"- Stuck / incomplete | 卡住: **{stuck}/{total}** ({_pct(stuck, total)})",
        f"- Runs with defects | 有缺陷的运行: **{with_defects}/{total}** ({_pct(with_defects, total)})",
        f"- Validation failures | 校验失败: **{validation_failures}/{total}**",
        f"- Capability gaps flagged | 能力缺口提示: **{capability_hits}/{total}**",
        f"- Learner proposal batches | 产生 Learner 提案的运行: **{len(proposal_runs)}**",
        f"- Unique proposal ids | 去重提案数: **{len(unique_proposals)}**",
        "",
        "## Status Breakdown | 状态分布",
        "",
    ]
    for status, count in sorted(status_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- `{status}`: {count}")

    lines.extend(["", "## Worker Routing | 路由分布", ""])
    for worker, count in sorted(worker_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- `{worker}`: {count}")

    lines.extend(["", "## Top Defects | 主要缺陷", ""])
    if not defect_groups:
        lines.append("_No defects recorded. | 未记录缺陷。_")
    else:
        for defect_key, count, examples in defect_groups[:15]:
            lines.append(f"### `{defect_key}` — {count} runs")
            for example in examples:
                lines.append(f"- Example | 示例: `{example}`")
            lines.append("")

    lines.extend(["## Scenario Hotspots | 问题场景", ""])
    scenario_defects: Counter[str] = Counter()
    for summary in summaries:
        if summary.defects:
            scenario_defects[summary.scenario_id] += 1
    if not scenario_defects:
        lines.append("_All scenarios clean in this batch. | 本批次场景均无缺陷。_")
    else:
        for scenario_id, count in scenario_defects.most_common(10):
            lines.append(f"- `{scenario_id}`: {count} defective runs")

    lines.extend(["", "## Recommended Fixes | 建议修改", ""])
    recommendations = build_recommendations(result)
    if not recommendations:
        lines.append("- No urgent fixes from this batch. | 本批次暂无紧急修复项。")
    else:
        for index, item in enumerate(recommendations, start=1):
            lines.append(f"{index}. {item}")

    lines.extend(["", "## Copy-Paste Handoff | 复制给 Agent 的摘要", ""])
    lines.append("```text")
    lines.append(build_handoff_block(result))
    lines.append("```")

    lines.extend(["", "## Failed / Blocked / Stuck Runs | 失败、阻断与卡住明细", ""])
    problem_runs = [
        item
        for item in summaries
        if item.status in {"FAILED", "BLOCKED", "AWAITING_REVIEW", "AWAITING_FINAL_FEEDBACK", "ACTIVE"}
        or item.defects
    ]
    if not problem_runs:
        lines.append("_None. | 无。_")
    else:
        for item in problem_runs[:40]:
            lines.append(
                f"- `{item.run_id}` | `{item.scenario_id}` | status=`{item.status}` | "
                f"defects={item.defects or ['—']}"
            )
        if len(problem_runs) > 40:
            lines.append(f"- … and {len(problem_runs) - 40} more")

    if unique_proposals:
        lines.extend(["", "## Learner Proposals | Learner 提案", ""])
        lines.append("Review with: `pah proposals pending`")
        lines.append("")
        for proposal_id in unique_proposals[:30]:
            lines.append(f"- `{proposal_id}`")
        if len(unique_proposals) > 30:
            lines.append(f"- … and {len(unique_proposals) - 30} more")

    lines.append("")
    return "\n".join(lines)


def build_recommendations(result: BatchResult) -> list[str]:
    summaries = result.summaries
    recs: list[str] = []
    defect_keys = Counter()
    for summary in summaries:
        for defect in summary.defects:
            defect_keys[defect.split(":", 1)[0]] += 1

    if defect_keys.get("run_blocked", 0) > 0:
        recs.append(
            "Reset per-run budget in dev-batch or raise config/budget.yaml limits "
            "（批量测试应隔离预算，或调高 budget 限额）"
        )
    if defect_keys.get("run_failed", 0) > 0:
        recs.append(
            "Investigate graph failures and add regression tests for failing scenarios "
            "（排查 LangGraph 失败路径并补回归测试）"
        )
    if defect_keys.get("validation_failed", 0) > 0:
        recs.append(
            "Tighten Creator/Searcher output validation or improve mock prompts "
            "（加强输出校验或改进 mock 提示词）"
        )
    if defect_keys.get("plan_invalid", 0) > 0:
        recs.append(
            "Fix orchestrator plan schema/normalization so plans validate consistently "
            "（修复 Orchestrator 计划规范化与校验）"
        )
    if defect_keys.get("missing_capability_warning", 0) > 0:
        recs.append(
            "Expand capability_brief gap patterns for account/publish/payment commands "
            "（扩展 capability_brief 的缺口检测规则）"
        )
    if defect_keys.get("incomplete_run", 0) > 0:
        recs.append(
            "Ensure batch auto-resume handles all interrupt types in dev-batch channel "
            "（确保 dev-batch 能自动走完所有 interrupt）"
        )
    if defect_keys.get("capability_gaps", 0) > 0 and defect_keys.get("missing_capability_warning", 0) == 0:
        recs.append(
            "Surface capability gaps earlier in Dev Lab UI and orchestrator prompts "
            "（在 Dev Lab 与 Orchestrator 提示中更早展示能力边界）"
        )
    return recs


def build_handoff_block(result: BatchResult) -> str:
    summaries = result.summaries
    total = len(summaries)
    completed = sum(1 for item in summaries if item.status == "COMPLETED")
    with_defects = sum(1 for item in summaries if item.defects)
    top_defects = _group_defects(summaries)[:8]
    lines = [
        f"PAHS dev-batch: {total} runs, {completed} completed, {with_defects} with defects.",
        f"mock_llm={result.mock_llm}, learner={result.with_learner}",
        "Top defects:",
    ]
    for key, count, examples in top_defects:
        example_text = ", ".join(examples[:2]) if examples else "n/a"
        lines.append(f"- {key}: {count}x (e.g. {example_text})")
    lines.append("Recommended fixes:")
    for item in build_recommendations(result)[:6]:
        lines.append(f"- {item}")
    lines.append("Please fix the highest-frequency defects first.")
    return "\n".join(lines)


def default_report_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return ensure_data_dir() / f"dev_batch_report_{stamp}.md"


def write_report(result: BatchResult, path: Path | None = None) -> Path:
    target = path or default_report_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_markdown_report(result), encoding="utf-8")
    return target
