"""Tool implementations used by Searcher and Executor."""

from __future__ import annotations

from typing import Any, Callable

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


def call_tool(name: str, **kwargs: Any) -> Any:
    impl = TOOL_IMPLS.get(name)
    if impl is None:
        raise KeyError(f"Unknown tool: {name}")
    return impl(**kwargs)
