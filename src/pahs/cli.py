"""PAHS command-line interface."""

from __future__ import annotations

import json

import typer

from pahs.env import load_project_env

load_project_env()

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
tools_app = typer.Typer(help="Builder staging tools.")
externals_app = typer.Typer(help="External local agents and bridges.")
app.add_typer(proposals_app, name="proposals")
app.add_typer(tools_app, name="tools")
app.add_typer(externals_app, name="externals")


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


@app.command("plan-preview")
def plan_preview(command: str) -> None:
    """Preview internal ExecutionPlan (orchestrator task table) without running."""
    from pahs.planning.orchestrator_planner import build_execution_plan
    from pahs.planning.step_router import validation_report
    from pahs.routing.task_classifier import classify_command

    classified = classify_command(command)
    plan = build_execution_plan(
        command,
        routing_context=classified["routing_context"],
        triage_result=classified["triage_result"],
        worker=classified["worker"],
        execution_mode=classified["execution_mode"],
        complexity_band=classified["complexity_band"],
        orchestrator_profile=classified["orchestrator_profile"],
        task_type=classified["task_type"],
        prefer_llm=True,
    )
    payload = {
        "command": command,
        "plan_source": plan.source,
        "execution_plan": plan.to_storage_dict(),
        "validation": validation_report(plan),
    }
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command("route-preview")
def route_preview(command: str) -> None:
    """Preview routing, model choice, and cost estimate without running."""
    from pahs.external.registry import match_external_agent

    classified = classify_command(command)
    routing = route_model(classified["routing_context"])
    cost = estimate_run_cost(classified["routing_context"], routing)
    standards = load_standards_for_task(classified["task_type"])
    external = match_external_agent(command)
    payload = {
        "command": command,
        "task_type": classified["task_type"],
        "complexity_band": classified["complexity_band"],
        "orchestrator_profile": classified["orchestrator_profile"],
        "worker": classified["worker"],
        "execution_mode": classified["execution_mode"],
        "external_match": external.name if external else None,
        "routing_decision": routing,
        "cost_estimate": cost,
        "standards_paths": standards["paths"],
    }
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@app.command("llm-status")
def llm_status() -> None:
    """Show whether PAHS will use DeepSeek or mock LLM."""
    from pahs.providers.router import llm_status as status_payload

    typer.echo(json.dumps(status_payload(), ensure_ascii=False, indent=2))


@app.command("search-route-preview")
def search_route_preview(
    query: str,
    user_task: str = typer.Option("", "--task", help="Full user task (defaults to query)"),
) -> None:
    """Preview smart search routing without calling search APIs."""
    from pahs.env import load_project_env
    from pahs.agents.search_router import route_search_task

    load_project_env()
    decision = route_search_task(query, user_task=user_task or query)
    typer.echo(json.dumps(decision.to_dict(), ensure_ascii=False, indent=2))


@app.command("search-test")
def search_test(
    query: str,
    provider: str = typer.Option("", "--provider", help="Override provider for this test"),
) -> None:
    """Test step-1 web search (Perplexity / Tavily / mock) without full LangGraph run."""
    from pahs.env import load_project_env
    from pahs.agents.search_router import route_search_task
    from pahs.tools.search_web import _resolve_provider, search_web

    load_project_env()
    mode = _resolve_provider()
    typer.echo(f"Search mode setting: {mode}")

    chosen = provider.strip() or None
    if mode == "smart" and not chosen:
        decision = route_search_task(query, user_task=query)
        chosen = decision.provider
        typer.echo(json.dumps({"route": decision.to_dict()}, ensure_ascii=False, indent=2))

    result = search_web(query, provider=chosen)
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2, default=str))


@app.command("search-status")
def search_status() -> None:
    """Show which search provider PAHS will use."""
    import os

    from pahs.env import load_project_env
    from pahs.tools.search_web import _resolve_provider

    load_project_env()
    mode = _resolve_provider()
    payload = {
        "search_mode": mode,
        "search_provider_setting": os.getenv("SEARCH_PROVIDER", "auto"),
        "perplexity_api_key_set": bool(os.getenv("PERPLEXITY_API_KEY", "").strip()),
        "perplexity_model": os.getenv("PERPLEXITY_MODEL", "sonar"),
        "tavily_api_key_set": bool(os.getenv("TAVILY_API_KEY", "").strip()),
        "search_route_use_llm": os.getenv("SEARCH_ROUTE_USE_LLM", "false"),
    }
    if mode == "smart":
        payload["routing"] = (
            "Searcher scores each query (simple → Tavily, deep research → Perplexity). "
            "Set SEARCH_ROUTE_USE_LLM=true to refine gray-zone tasks with DeepSeek."
        )
    else:
        payload["resolved_provider"] = mode if mode != "auto" else (
            "perplexity"
            if os.getenv("PERPLEXITY_API_KEY", "").strip()
            else "tavily"
            if os.getenv("TAVILY_API_KEY", "").strip()
            else "mock"
        )
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


@tools_app.command("staging")
def tools_staging() -> None:
    """List staged Builder tools."""
    from pahs.builder.tool_manifest import list_staging_manifests

    rows = list_staging_manifests()
    if not rows:
        typer.echo("No staged tools.")
        typer.echo("没有 staging 工具。")
        return
    for row in rows:
        typer.echo(
            f"- {row.name} status={row.status} test_passed={row.test_passed} agent={row.agent}"
        )


@tools_app.command("draft")
def tools_draft(
    requirement: str,
    agent: str = typer.Option("executor", "--agent", help="Target agent for the tool."),
) -> None:
    """Generate a staged tool and run sandbox tests (mock Builder)."""
    from pahs.builder.builder import draft_tool

    try:
        manifest = draft_tool(requirement, agent=agent)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2))
    typer.echo("Tool is in staging and NOT callable by Orchestrator until approved.")
    typer.echo("工具已在 staging，批准前 Orchestrator 不能调用。")


@tools_app.command("review")
def tools_review(tool_name: str) -> None:
    """Show staged tool code, tests, and manifest."""
    from pahs.builder.review import review_tool

    try:
        payload = review_tool(tool_name)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@tools_app.command("approve")
def tools_approve(tool_name: str) -> None:
    """Approve a staged tool and add it to the production registry."""
    from pahs.builder.review import approve_tool

    try:
        result = approve_tool(tool_name)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    typer.echo("Approved tool is now available to future production runs.")
    typer.echo("已批准，后续生产运行可调用该工具。")


@tools_app.command("reject")
def tools_reject(
    tool_name: str,
    reason: str = typer.Option(..., "--reason", "-r", help="Why this tool is rejected."),
) -> None:
    """Reject a staged tool."""
    from pahs.builder.review import reject_tool

    try:
        result = reject_tool(tool_name, reason=reason)
    except ValueError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))
    typer.echo("Rejected tool remains blocked from production.")
    typer.echo("已拒绝，生产环境仍不可调用。")


@externals_app.command("list")
def externals_list() -> None:
    """List configured external agents."""
    from pahs.external.registry import list_external_agents

    rows = list_external_agents(enabled_only=False)
    if not rows:
        typer.echo("No external agents configured.")
        typer.echo("没有配置外部 agent。")
        return
    for row in rows:
        enabled = row.config.get("enabled", False)
        typer.echo(
            f"- {row.name} enabled={enabled} type={row.type} description={row.description}"
        )


@externals_app.command("test")
def externals_test(agent_name: str, message: str) -> None:
    """Call an external agent directly for debugging."""
    from pahs.external.runner import run_external_agent

    try:
        result = run_external_agent(agent_name, message)
    except Exception as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(json.dumps(result, ensure_ascii=False, indent=2))


@app.command("dev-batch")
def dev_batch(
    runs: int = typer.Option(100, "--runs", "-n", help="Number of batch runs"),
    mock: bool = typer.Option(
        True,
        "--mock/--no-mock",
        help="Force mock LLM (recommended for 100x runs)",
    ),
    learner: bool = typer.Option(
        True,
        "--learner/--no-learner",
        help="Feed synthetic final feedback to Learner",
    ),
    output: str | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Markdown report path (default: data/dev_batch_report_<ts>.md)",
    ),
    scenario_file: str | None = typer.Option(
        None,
        "--scenarios",
        help="Custom scenarios YAML path",
    ),
) -> None:
    """Run automated Dev batch tests and write a defect report."""
    from pathlib import Path

    from pahs.devlab.batch_report import write_report
    from pahs.devlab.batch_runner import run_batch, save_batch_json

    db.init_db()
    scenario_path = Path(scenario_file) if scenario_file else None
    output_path = Path(output) if output else None

    typer.echo(f"Starting dev batch: {runs} runs (mock={mock}, learner={learner})")
    typer.echo(f"开始批量测试：{runs} 次（mock={mock}, learner={learner}）")

    def on_progress(done: int, total: int, summary: object) -> None:
        status = getattr(summary, "status", "?")
        scenario_id = getattr(summary, "scenario_id", "?")
        typer.echo(f"[{done}/{total}] {scenario_id} -> {status}")

    result = run_batch(
        runs=runs,
        mock_llm=mock,
        with_learner=learner,
        scenario_file=scenario_path,
        on_progress=on_progress,
    )

    report_path = write_report(result, output_path)
    json_path = save_batch_json(
        result,
        report_path.with_suffix(".json"),
    )

    completed = sum(1 for item in result.summaries if item.status == "COMPLETED")
    defective = sum(1 for item in result.summaries if item.defects)
    typer.echo("")
    typer.echo(f"Done. Completed {completed}/{runs}, defective {defective}/{runs}")
    typer.echo(f"完成。成功 {completed}/{runs}，有缺陷 {defective}/{runs}")
    typer.echo(f"Report: {report_path}")
    typer.echo(f"JSON:   {json_path}")
    typer.echo("")
    typer.echo("Copy the 'Copy-Paste Handoff' section from the report back to your agent.")


@app.command("dev-ui")
def dev_ui(
    host: str = typer.Option("127.0.0.1", help="Bind host"),
    port: int = typer.Option(8765, help="Bind port"),
) -> None:
    """Start local Dev Lab chat UI for testing (http://127.0.0.1:8765)."""
    import socket

    from pahs.devlab.server import run_server
    from pahs.env import load_project_env

    load_project_env()
    db.init_db()

    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        probe.bind((host, port))
    except OSError:
        typer.echo(f"Port {port} is already in use.", err=True)
        typer.echo(f"Stop the old server: lsof -ti:{port} | xargs kill -9", err=True)
        typer.echo(f"Or use another port: pah dev-ui --port {port + 1}", err=True)
        raise typer.Exit(code=1) from None
    finally:
        probe.close()

    url = f"http://{host}:{port}"
    typer.echo(f"PAHS Dev Lab running at {url}")
    typer.echo("Open this URL in your browser to chat and watch architecture progress.")
    typer.echo("在浏览器打开上述地址，进行聊天测试并查看实时架构进度。")
    run_server(host=host, port=port)


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
