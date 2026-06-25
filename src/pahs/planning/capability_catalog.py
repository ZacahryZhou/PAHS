"""Project capability catalog for the Orchestrator planner."""

from __future__ import annotations

from typing import Any

from pahs.external.registry import list_external_agents
from pahs.harness.tools import all_approved_tools


def build_capability_catalog() -> list[dict[str, Any]]:
    """List tools/agents the orchestrator may assign in a plan."""
    catalog: list[dict[str, Any]] = []

    for spec in list_external_agents(enabled_only=True):
        catalog.append(
            {
                "id": spec.name,
                "kind": "external",
                "worker": "external",
                "external_agent": spec.name,
                "tool": spec.name,
                "description": spec.description,
            }
        )

    worker_tools: dict[str, list[dict[str, str]]] = {
        "searcher": [],
        "creator": [],
        "executor": [],
    }
    for tool in all_approved_tools().values():
        entry = {
            "tool": tool.name,
            "description": tool.description,
        }
        if tool.agent in worker_tools:
            worker_tools[tool.agent].append(entry)

    catalog.append(
        {
            "id": "searcher",
            "kind": "internal",
            "worker": "searcher",
            "tool": "search_web",
            "description": "Web research with Search Router (Tavily/Perplexity) + LLM summary.",
            "tools": worker_tools["searcher"],
        }
    )
    catalog.append(
        {
            "id": "creator",
            "kind": "internal",
            "worker": "creator",
            "tool": "generate_content",
            "description": "Write text deliverables: copy, reports, explanations.",
            "tools": worker_tools["creator"],
        }
    )
    catalog.append(
        {
            "id": "executor",
            "kind": "internal",
            "worker": "executor",
            "description": "Run code or analysis.",
            "execution_modes": ["CODE", "ANALYSIS", "DEEP_THINK"],
            "tools": worker_tools["executor"],
        }
    )
    return catalog


def format_catalog_for_prompt(catalog: list[dict[str, Any]]) -> str:
    lines = ["Available capabilities:"]
    for item in catalog:
        worker = item.get("worker", "?")
        tool = item.get("tool") or item.get("tools") or item.get("execution_modes")
        lines.append(f"- {item['id']} ({worker}): {item.get('description', '')} | {tool}")
    return "\n".join(lines)
