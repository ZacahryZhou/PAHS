"""Approved production tool registry — staging tools are excluded."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pahs.builder.tool_manifest import load_production_registry


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
        agent="executor",
        description="Execute Python in a sandbox.",
        cost_per_call=0.0,
        sandbox=True,
    ),
    "read_file": ToolDescriptor(
        name="read_file",
        agent="executor",
        description="Read a file from the PAHS data directory.",
        cost_per_call=0.0,
    ),
    "write_file": ToolDescriptor(
        name="write_file",
        agent="executor",
        description="Write a file into the PAHS data directory.",
        cost_per_call=0.0,
    ),
}


def _approved_builtin_descriptors() -> dict[str, ToolDescriptor]:
    descriptors: dict[str, ToolDescriptor] = {}
    for name, item in load_production_registry().items():
        if item.get("status") != "APPROVED":
            continue
        descriptors[name] = ToolDescriptor(
            name=name,
            agent=str(item.get("agent", "executor")),
            description=str(item.get("description", "Approved Builder tool.")),
            cost_per_call=float(item.get("cost_per_call", 0.0)),
            sandbox=bool(item.get("sandbox", True)),
            status="APPROVED",
        )
    return descriptors


def all_approved_tools() -> dict[str, ToolDescriptor]:
    merged = dict(APPROVED_TOOLS)
    merged.update(_approved_builtin_descriptors())
    return merged


def list_tools_for_agent(agent_id: str) -> list[ToolDescriptor]:
    return [
        tool
        for tool in all_approved_tools().values()
        if tool.agent == agent_id and tool.status == "APPROVED"
    ]


def get_tool(name: str) -> ToolDescriptor | None:
    tool = all_approved_tools().get(name)
    if tool and tool.status == "APPROVED":
        return tool
    return None


def is_staging_tool_name(name: str) -> bool:
    from pahs.builder.tool_manifest import manifest_path_for_staging

    return manifest_path_for_staging(name).exists()
