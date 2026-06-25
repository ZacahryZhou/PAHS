"""Safe Python execution for ANALYSIS/CODE modes."""

from __future__ import annotations

import io
from contextlib import redirect_stdout
from typing import Any


ALLOWED_BUILTINS = {
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
    "len": len,
    "range": range,
    "print": print,
    "round": round,
}


def run_python(code: str, *, timeout_hint: str = "sandbox") -> dict[str, Any]:
    stdout = io.StringIO()
    local_vars: dict[str, Any] = {}
    try:
        with redirect_stdout(stdout):
            exec(code, {"__builtins__": ALLOWED_BUILTINS}, local_vars)
        return {
            "ok": True,
            "stdout": stdout.getvalue().strip(),
            "locals": {key: value for key, value in local_vars.items() if not key.startswith("_")},
            "timeout_hint": timeout_hint,
        }
    except Exception as exc:
        return {
            "ok": False,
            "stdout": stdout.getvalue().strip(),
            "error": str(exc),
            "timeout_hint": timeout_hint,
        }
