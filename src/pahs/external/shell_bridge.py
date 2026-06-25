"""Generic shell-based external project bridge."""

from __future__ import annotations

import os
import subprocess
from typing import Any

from pahs.external.registry import ExternalAgentSpec


def run_shell_bridge(spec: ExternalAgentSpec, prompt: str) -> dict[str, Any]:
    command = spec.config.get("command")
    if not command:
        raise RuntimeError(f"Shell external `{spec.name}` is missing `command`.")

    if isinstance(command, str):
        cmd = [command]
    else:
        cmd = [str(part).replace("$PAHS_PROMPT", prompt) for part in command]

    cwd = spec.config.get("working_directory")
    env = os.environ.copy()
    env["PAHS_PROMPT"] = prompt
    env["PAHS_EXTERNAL_AGENT"] = spec.name

    timeout = int(spec.config.get("timeout_seconds", 300))
    result = subprocess.run(
        cmd,
        cwd=os.path.expanduser(str(cwd)) if cwd else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
        env=env,
    )
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "text": stdout or stderr or "Shell bridge returned no output.",
        "raw_stdout": stdout,
        "raw_stderr": stderr,
        "command": cmd,
        "external_type": "shell",
        "external_name": spec.name,
    }
