"""Bridge to local OpenClaw CLI."""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import Any

from pahs.external.registry import ExternalAgentSpec


def run_openclaw(spec: ExternalAgentSpec, prompt: str) -> dict[str, Any]:
    binary = str(spec.config.get("binary", "openclaw"))
    if shutil.which(binary) is None:
        raise RuntimeError(f"`{binary}` not found on PATH.")

    cmd = [binary, "agent"]
    agent_id = str(spec.config.get("default_agent", "main"))
    cmd.extend(["--agent", agent_id])
    if spec.config.get("use_local", True):
        cmd.append("--local")
    if spec.config.get("use_json", True):
        cmd.append("--json")
    cmd.extend(["-m", prompt])

    timeout = int(spec.config.get("timeout_seconds", 600))
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()

    parsed: dict[str, Any] | None = None
    text = stdout
    if stdout:
        try:
            parsed = json.loads(stdout)
            payloads = parsed.get("payloads") or []
            if payloads and isinstance(payloads[0], dict):
                text = str(payloads[0].get("text", text))
        except json.JSONDecodeError:
            parsed = None

    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "text": text or stderr or "OpenClaw returned no output.",
        "raw_stdout": stdout,
        "raw_stderr": stderr,
        "parsed_json": parsed,
        "command": cmd,
        "external_type": "openclaw",
        "external_name": spec.name,
    }
