"""Approved production tool registry — staging tools are excluded."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolDescriptor:
    name: str
    agent: str
    description: str
    cost_per_call: float = 0.0
    requires_verification: bool = True
    sandbox: bool = False
    status: str = "APPROVED"


APPROVED_TOOLS: dict[str, ToolDescriptor] = {
    "generate_content": ToolDescriptor(
        name="generate_content",
        agent="creator",
        description="Generate text content for the current task.",
        cost_per_call=0.001,
    ),
    "search_web": ToolDescriptor(
        name="search_web",
        agent="searcher",
        description="Search the web for fresh information.",
        cost_per_call=0.001,
    ),
    "run_python": ToolDescriptor(
        name="run_python",
        agent="code",
        description="Execute Python in a sandbox.",
        cost_per_call=0.0,
        sandbox=True,
    ),
}


def list_tools_for_agent(agent_id: str) -> list[ToolDescriptor]:
    return [
        tool
        for tool in APPROVED_TOOLS.values()
        if tool.agent == agent_id and tool.status == "APPROVED"
    ]


def get_tool(name: str) -> ToolDescriptor | None:
    tool = APPROVED_TOOLS.get(name)
    if tool and tool.status == "APPROVED":
        return tool
    return None
