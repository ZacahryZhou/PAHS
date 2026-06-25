"""Searcher agent — uses search_web tool and optional DeepSeek summary."""

from __future__ import annotations

from pahs.graph.state import PAHSState
from pahs.providers.router import llm_complete
from pahs.tools.registry import call_tool


def searcher_node(state: PAHSState) -> dict:
    command = state["user_command"]
    feedback = state.get("user_milestone_review", "").strip()
    query = feedback or command
    result = call_tool("search_web", query=query)
    sources = result.get("sources", [])
    model = (state.get("routing_decision") or {}).get("selected_model", "deepseek-chat")

    summary = llm_complete(
        system=(
            "You are PAHS Searcher. Summarize the research findings with sources. "
            "Include URLs when available."
        ),
        user=(
            f"User task: {command}\n"
            f"Search query: {query}\n"
            f"Raw search summary: {result.get('summary', '')}\n"
            f"Sources: {sources}"
        ),
        model=model,
        run_id=state["run_id"],
        phase="searcher_summary",
    )
    output = (
        "[Searcher Output]\n"
        f"Query: {query}\n"
        f"Provider: {result.get('provider')}\n"
        f"Model: {model}\n\n"
        f"{summary}"
    )
    if result.get("warning"):
        output += f"\n\nWarning: {result['warning']}"
    return {
        "milestone_output": output,
        "sources": sources,
        "status": "EXECUTED",
    }
