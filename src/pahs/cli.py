"""PAHS command-line interface."""

from __future__ import annotations

import json

import typer

from pahs.gateway.run_ids import new_run_id
from pahs.graph.runner import resume_run, start_run
from pahs.harness.rules import RuleEngine
from pahs.harness.test_reset import reset_all_test_data
from pahs.storage import db

app = typer.Typer(help="Personal Agent Harness System (PAHS)")


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
        f"- events: {summary['events']}"
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
