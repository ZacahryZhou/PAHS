"""Sandbox execution for staged Builder tools."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run_staging_tests(tool_dir: Path) -> tuple[bool, str]:
    test_file = tool_dir / "test_tool.py"
    if not test_file.exists():
        return False, "Missing test_tool.py"

    result = subprocess.run(
        [sys.executable, str(test_file)],
        cwd=str(tool_dir),
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    output = (result.stdout or "") + (result.stderr or "")
    return result.returncode == 0, output.strip()
