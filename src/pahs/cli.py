"""PAHS command-line interface."""

from __future__ import annotations

import json

import typer

from pahs.gateway.run_ids import new_run_id
from pahs.graph.runner import resume_run, start_run
from pahs.harness.budget import BudgetManager
from pahs.harness.rules import RuleEngine
from pahs.harness.test_reset import reset_all_test_data
from pahs.routing.cost_estimator import estimate_run_cost
from pahs.routing.llm_router import route_model
from pahs.routing.standards_loader import load_standards_for_task
from pahs.routing.task_classifier import classify_command
from pahs.storage import db

app = typer.Typer(help="Personal Agent Harness System (PAHS)")
proposals_app = typer.Typer(help="Review Learner proposals.")
app.add_typer(proposals_app, name="proposals")


@app.command("init-db")
def init_db() -> None:
    """Initialize SQLite schema."""
    path = db.init_db()
    typer.echo(f"Database initialized: {path}")


@app.command("run")
def run_command(command: str) -> None:
    """Start a new run from the CLI."""
    db.init_db()
    run_id = new_run_id()
    typer.echo(f"Starting run: {run_id}")
    result = start_run(run_id, command, channel="cli")

    if result.get("__interrupt__"):
        typer.echo("\nRun paused for review. Use `pah pending` and `pah reply`.")
        typer.echo("运行已暂停，等待审核。请使用 `pah pending` 和 `pah reply`。")
    else:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2, default=str))


@app.command("status")
def status(run_id: str) -> None:
    """Show run status."""
    db.init_db()
    row = db.get_run(run_id)
    if row is None:
        raise typer.Exit(code=1)
    typer.echo(json.dumps(row, ensure_ascii=False, indent=2))


@app.command("pending")
def pending() -> None:
    """List pending reviews."""
    db.init_db()
    rows = db.list_pending_reviews()
    if not rows:
        typer.echo("No pending reviews.")
        typer.echo("没有待审核任务。")
        return
    for row in rows:
        typer.echo(
            f"- run_id={row['run_id']} type={row['review_type']} command={row['command']}"
        )


@app.command("reply")
def reply(run_id: str, message: str) -> None:
    """Reply to the current pending review for a run."""
    db.init_db()
    try:
        result = resume_run(run_id, message, channel="cli")
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    if result.get("__interrupt__"):
        typer.echo("\nRun paused again for final feedback.")
        typer.echo("运行再次暂停，等待总反馈。")
        typer.echo("Example | 示例: pah reply <run_id> \"looks good\"")
    elif result.get("status") == "COMPLETED":
        typer.echo("\nRun completed.")
        typer.echo("运行已完成。")
        proposal_ids = result.get("learner_proposals") or []
        if proposal_ids:
            typer.echo(f"Learner created {len(proposal_ids)} pending proposal(s).")
            typer.echo(f"Learner 已生成 {len(proposal_ids)} 条待批准提案。")
            typer.echo("Check with: pah proposals pending")
            typer.echo("查看：pah proposals pending")
    else:
        typer.echo(json.dumps(result, ensure_ascii=False, indent=2, default=str))


@app.command("events")
def events(run_id: str) -> None:
    """Show harness events for a run."""
    db.init_db()
    rows = db.list_run_events(run_id)
    if not rows:
        typer.echo("No events found.")
        typer.echo("没有找到事件。")
        raise typer.Exit(code=1)
    typer.echo(json.dumps(rows, ensure_ascii=False, indent=2))


@app.command("rules-show")
def rules_show(scope: str = typer.Argument("global", help="global | creator | searcher")) -> None:
    """Show which rule files would load for a scope."""
    engine = RuleEngine()
    if scope == "creator":
        pack = engine.load_for_agent("creator")
    elif scope == "searcher":
        pack = engine.load_for_agent("searcher")
    else:
        pack = engine.load_global()
    typer.echo("Loaded rule files:")
    for path in pack.paths:
        typer.echo(f"- {path}")


@app.command("route-preview")
def route_preview(command: str) -> None:
    """Preview routing, model choice, and cost estimate without running."""
    classified = classify_command(command)
    routing = route_model(classified["routing_context"])
    cost = estimate_run_cost(classified["routing_context"], routing)
    standards = load_standards_for_task(classified["task_type"])
    payload = {
        "command": command,
        "task_type": classified["task_type"],
        "complexity_band": classified["complexity_band"],
        "orchestrator_profile": classified["orchestrator_profile"],
        "worker": classified["worker"],
        "execution_mode": classified["execution_mode"],
        "routing_decision": routing,
        "cost_estimate": cost,
        "standards_paths": standards["paths"],
    }
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command("costs-today")
def costs_today() -> None:
    """Show in-process daily budget counters (mock Week 4)."""
    snapshot = BudgetManager("preview").to_dict()
    typer.echo("Daily budget snapshot | 今日预算快照")
    typer.echo(json.dumps(snapshot, ensure_ascii=False, indent=2))


@app.command("feedback")
def feedback(run_id: str, message: str) -> None:
    """Submit final feedback for a completed run and create pending proposals."""
    db.init_db()
    run = db.get_run(run_id)
    if run is None:
        typer.echo(f"Unknown run_id={run_id}")
        raise typer.Exit(code=1)
    if run.get("status") != "COMPLETED":
        typer.echo("Run is not completed yet. Use `pah reply` during final feedback.")
        typer.echo("任务尚未完成。请在 final feedback 阶段使用 `pah reply`。")
        raise typer.Exit(code=1)

    from pahs.learning.learner import learn_from_final_feedback

    proposals = learn_from_final_feedback(run_id, message)
    typer.echo(f"Created {len(proposals)} pending proposal(s).")
    typer.echo(f"已创建 {len(proposals)} 条待批准提案。")
    for item in proposals:
        typer.echo(f"- {item.proposal_id} [{item.proposal_type}] {item.title}")


@proposals_app.command("pending")
def proposals_pending() -> None:
    """List pending Learner proposals."""
    db.init_db()
    from pahs.learning.proposals import list_pending_proposals

    rows = list_pending_proposals()
    if not rows:
        typer.echo("No pending proposals.")
        typer.echo("没有待批准提案。")
        return
    for row in rows:
        typer.echo(
            f"- {row.proposal_id} run={row.run_id} type={row.proposal_type} title={row.title}"
        )


@proposals_app.command("approve")
def proposals_approve(proposal_id: str) -> None:
    """Approve a pending proposal and apply it to future runs."""
    db.init_db()
    from pahs.learning.approvals import approve_proposal

    try:
        result = approve_proposal(proposal_id)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    typer.echo("Approved. Future runs can use the updated standard/rule.")
    typer.echo("已批准。后续任务会使用更新后的标准/规则。")


@proposals_app.command("reject")
def proposals_reject(
    proposal_id: str,
    reason: str = typer.Option(..., "--reason", "-r", help="Why this proposal is rejected."),
) -> None:
    """Reject a pending proposal."""
    db.init_db()
    from pahs.learning.approvals import reject_proposal

    try:
        result = reject_proposal(proposal_id, reason=reason)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    typer.echo("Rejected proposal stored with reason.")
    typer.echo("已拒绝并保存原因。")


@app.command("telegram")
def telegram_bot() -> None:
    """Start the Telegram gateway bot."""
    from pahs.gateway.telegram_adapter import run_telegram_bot

    try:
        run_telegram_bot()
    except RuntimeError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc


@app.command("reset-test")
def reset_test(
    force: bool = typer.Option(
        False,
        "--force",
        help="Skip typed confirmation (still requires first yes).",
    ),
) -> None:
    """Delete all local test runs, pending reviews, events, and checkpoints."""
    db.init_db()
    summary = db.summarize_test_data()

    typer.echo("PAHS test reset | 测试数据清理")
    typer.echo(
        f"- runs: {summary['runs']}\n"
        f"- pending reviews: {summary['pending_reviews']}\n"
        f"- review rows: {summary['review_rows']}\n"
        f"- events: {summary['events']}\n"
        f"- proposals: {summary.get('proposals', 0)}"
    )

    if summary["runs"] == 0 and summary["review_rows"] == 0 and summary["events"] == 0:
        typer.echo("\nNothing to delete.")
        typer.echo("没有可删除的数据。")
        raise typer.Exit(code=0)

    typer.echo(
        "\nThis will delete ALL runs, pending reviews, run events, LangGraph checkpoints,"
    )
    typer.echo("and files under data/outputs/.")
    typer.echo("将删除所有 runs、pending、events、checkpoints 和 data/outputs/ 下文件。")
    typer.echo("Telegram user channel mappings will be kept.")
    typer.echo("Telegram 用户映射会保留。")

    if not typer.confirm("\nStep 1/2: Continue?", default=False):
        typer.echo("Cancelled.")
        typer.echo("已取消。")
        raise typer.Exit(code=1)

    if not force:
        typed = typer.prompt("Step 2/2: Type DELETE ALL to confirm")
        if typed.strip() != "DELETE ALL":
            typer.echo("Confirmation failed. Nothing was deleted.")
            typer.echo("确认失败，未删除任何数据。")
            raise typer.Exit(code=1)

    result = reset_all_test_data(include_outputs=True)
    typer.echo("\nTest data cleared.")
    typer.echo("测试数据已清理。")
    typer.echo(
        f"- deleted runs: {result['runs']}\n"
        f"- deleted review rows: {result['review_rows']}\n"
        f"- deleted events: {result['events']}\n"
        f"- checkpoints cleared: {result['checkpoints_cleared']}\n"
        f"- output files removed: {result['output_files_removed']}"
    )
    typer.echo("\nYou can verify with: pah pending")
    typer.echo("可用 `pah pending` 验证。")


if __name__ == "__main__":
    app()
