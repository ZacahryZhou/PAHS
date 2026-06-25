"""Bridge to PIP video generation pipeline."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pahs.external.registry import ExternalAgentSpec


def run_pip(spec: ExternalAgentSpec, prompt: str) -> dict[str, Any]:
    project_dir = Path(os.path.expanduser(str(spec.config.get("project_dir", "~/Desktop/PIP"))))
    venv_python = project_dir / ".venv" / "bin" / "python"
    python_bin = str(venv_python if venv_python.exists() else "python")

    payload = {
        "raw_prompt": prompt,
        "channel": "pahs",
        "user_id": "pahs",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    timeout = int(spec.config.get("timeout_seconds", 3600))
    mock = bool(spec.config.get("mock", False))
    if os.getenv("PAHS_DEV_BATCH", "").lower() in {"1", "true", "yes"}:
        mock = True
        timeout = min(timeout, 60)
    skip_approval = bool(spec.config.get("skip_approval", True))
    stop_after = spec.config.get("stop_after")

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        payload_path = handle.name

    cmd = [
        python_bin,
        "-m",
        "video_pipeline.main",
        "--payload",
        payload_path,
    ]
    if mock:
        cmd.append("--mock")
    if skip_approval:
        cmd.append("--skip-approval")
    if stop_after:
        cmd.extend(["--stop-after", str(stop_after)])

    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env={**os.environ, "PYTHONPATH": str(project_dir / "src")},
        )
    finally:
        Path(payload_path).unlink(missing_ok=True)

    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    text = stdout or stderr or "PIP returned no output."

    job_id = None
    for line in stdout.splitlines():
        if line.startswith("Job ID:"):
            job_id = line.split(":", 1)[1].strip()
        if line.startswith("Job created:"):
            text = f"{line}\n{text}"

    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "text": text,
        "job_id": job_id,
        "raw_stdout": stdout,
        "raw_stderr": stderr,
        "command": cmd,
        "external_type": "pip",
        "external_name": spec.name,
        "payload": payload,
        "mock": mock,
    }
