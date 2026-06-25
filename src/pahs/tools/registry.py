"""Tool implementations used by Searcher and Executor."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Callable

from pahs.builder.tool_manifest import BUILTIN_DIR, load_production_registry
from pahs.harness.tools import is_staging_tool_name
from pahs.tools.file_tools import read_file, write_file
from pahs.tools.python_sandbox import run_python
from pahs.tools.search_web import search_web

ToolFn = Callable[..., dict[str, Any] | str]

TOOL_IMPLS: dict[str, ToolFn] = {
    "search_web": search_web,
    "run_python": run_python,
    "read_file": read_file,
    "write_file": write_file,
}


def _load_builtin_tool(name: str) -> ToolFn | None:
    registry = load_production_registry()
    entry = registry.get(name)
    if not entry or entry.get("status") != "APPROVED":
        return None

    tool_file = BUILTIN_DIR / name / "tool.py"
    if not tool_file.exists():
        return None

    spec = importlib.util.spec_from_file_location(f"pahs_builtin_{name}", tool_file)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    fn = getattr(module, entry.get("function", "run"), None)
    return fn if callable(fn) else None


def call_tool(name: str, **kwargs: Any) -> Any:
    if is_staging_tool_name(name):
        raise PermissionError(
            f"Tool `{name}` is in staging and cannot be called by production orchestration."
        )

    impl = TOOL_IMPLS.get(name)
    if impl is None:
        impl = _load_builtin_tool(name)
    if impl is None:
        raise KeyError(f"Unknown or unapproved tool: {name}")
    return impl(**kwargs)
