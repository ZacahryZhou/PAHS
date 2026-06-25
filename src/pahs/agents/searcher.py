"""Searcher agent — route → search (Perplexity/Tavily) → LLM final answer."""

from __future__ import annotations

from pahs.agents.search_router import route_search_task
from pahs.planning.task_context import effective_task_prompt
from pahs.graph.state import PAHSState
from pahs.providers.router import llm_complete
from pahs.tools.registry import call_tool
from pahs.tools.search_web import _resolve_provider


def _format_sources(sources: list[dict]) -> str:
    if not sources:
        return "(no sources returned)"
    lines = []
    for index, source in enumerate(sources, start=1):
        title = source.get("title") or "Source"
        url = source.get("url") or ""
        snippet = source.get("snippet") or ""
        block = f"[{index}] {title}\nURL: {url}"
        if snippet:
            block += f"\nSnippet: {snippet}"
        lines.append(block)
    return "\n\n".join(lines)


def searcher_node(state: PAHSState) -> dict:
    command = state["user_command"]
    feedback = state.get("user_milestone_review", "").strip()
    query = effective_task_prompt(state)

    routing_context = state.get("routing_context") or {}
    search_mode = _resolve_provider()
    route_decision = None
    search_provider = search_mode

    if search_mode == "smart":
        route_decision = route_search_task(
            query,
            user_task=command,
            routing_context=routing_context,
            run_id=state["run_id"],
        )
        search_provider = route_decision.provider

    # Step 1 — web-grounded research (routed provider when smart mode)
    result = call_tool("search_web", query=query, provider=search_provider)
    sources = result.get("sources", [])
    provider = result.get("provider", search_provider)
    research_draft = str(
        result.get("research_draft") or result.get("summary") or ""
    ).strip()

    model = (state.get("routing_decision") or {}).get("selected_model", "deepseek-chat")

    route_block = ""
    if route_decision is not None:
        route_block = (
            f"Search route level: {route_decision.level}\n"
            f"Route score: {route_decision.score}\n"
            f"Route method: {route_decision.method}\n"
            f"Route dimensions: {route_decision.dimensions}\n"
            f"Route reasons: {'; '.join(route_decision.reasons)}\n\n"
        )

    # Step 2 — PAHS formats the final milestone answer (do not invent new facts)
    summary = llm_complete(
        system=(
            "You are PAHS Searcher (step 2 of 2).\n"
            "Step 1 already ran a web search provider and returned a research draft with sources.\n"
            "Your job:\n"
            "- Produce the FINAL answer for the user's task\n"
            "- Keep claims grounded in the research draft and sources\n"
            "- Include a Sources section with URLs\n"
            "- Prefer official documentation when available\n"
            "- Use the same language as the user unless they ask otherwise\n"
            "- Do not fabricate links or statistics"
        ),
        user=(
            f"User task:\n{command}\n\n"
            f"Search query:\n{query}\n\n"
            f"Search provider (step 1):\n{provider}\n\n"
            f"{route_block}"
            f"Research draft (step 1):\n{research_draft}\n\n"
            f"Sources (step 1):\n{_format_sources(sources)}"
        ),
        model=model,
        run_id=state["run_id"],
        phase="searcher_summary",
    )

    output = (
        "[Searcher Output]\n"
        f"Query: {query}\n"
        f"Search mode: {search_mode}\n"
        f"Search provider (step 1): {provider}\n"
        f"Final model (step 2): {model}\n"
    )
    if route_decision is not None:
        active = route_decision.dimensions.get("active_count", 0)
        output += (
            f"Route level: {route_decision.level} "
            f"(score {route_decision.score}, {active} Perplexity signals)\n"
        )
    output += f"\n{summary}"
    if result.get("warning"):
        output += f"\n\nWarning: {result['warning']}"

    search_step: dict = {
        "provider": provider,
        "model": result.get("model"),
        "usage": result.get("usage"),
        "source_count": len(sources),
        "search_mode": search_mode,
    }
    if route_decision is not None:
        search_step["route"] = route_decision.to_dict()

    return {
        "milestone_output": output,
        "sources": sources,
        "search_provider": provider,
        "search_step": search_step,
        "status": "EXECUTED",
    }
