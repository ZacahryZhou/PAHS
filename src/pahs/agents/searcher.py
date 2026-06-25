"""Searcher agent — uses search_web tool."""

from __future__ import annotations

from pahs.graph.state import PAHSState
from pahs.tools.registry import call_tool


def searcher_node(state: PAHSState) -> dict:
    command = state["user_command"]
    feedback = state.get("user_milestone_review", "").strip()
    query = feedback or command
    result = call_tool("search_web", query=query)
    sources = result.get("sources", [])
    output = (
        "[Searcher Output]\n"
        f"Query: {query}\n"
        f"Provider: {result.get('provider')}\n\n"
        f"{result.get('summary', '')}"
    )
    if result.get("warning"):
        output += f"\n\nWarning: {result['warning']}"
    return {
        "milestone_output": output,
        "sources": sources,
        "status": "EXECUTED",
    }
