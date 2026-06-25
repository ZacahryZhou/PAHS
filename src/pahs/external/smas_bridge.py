"""Bridge to SMAS Instagram post generator."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from pahs.external.registry import ExternalAgentSpec


def run_smas(spec: ExternalAgentSpec, prompt: str) -> dict[str, Any]:
    project_dir = Path(os.path.expanduser(str(spec.config.get("project_dir", "~/Desktop/SMAS"))))
    bridge = project_dir / "scripts" / "smas.sh"
    if not bridge.exists():
        raise RuntimeError(f"SMAS bridge not found: {bridge}")

    subcommand = str(spec.config.get("subcommand", "message"))
    timeout = int(spec.config.get("timeout_seconds", 900))
    cmd = [str(bridge), subcommand, prompt]

    result = subprocess.run(
        cmd,
        cwd=str(project_dir),
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
            text = str(parsed.get("text") or parsed.get("summary") or stdout)
            preview = parsed.get("preview_image")
            if preview:
                text += f"\n\nPreview image: {preview}"
            critic = parsed.get("critic")
            if isinstance(critic, dict) and critic.get("summary"):
                text += f"\n\nCritic: {critic['summary']}"
        except json.JSONDecodeError:
            parsed = None

    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "text": text or stderr or "SMAS returned no output.",
        "raw_stdout": stdout,
        "raw_stderr": stderr,
        "parsed_json": parsed,
        "command": cmd,
        "external_type": "smas",
        "external_name": spec.name,
    }
