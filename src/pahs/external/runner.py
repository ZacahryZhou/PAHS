"""Dispatch to configured external agents."""

from __future__ import annotations

from typing import Any

from pahs.external.openclaw_bridge import run_openclaw
from pahs.external.pip_bridge import run_pip
from pahs.external.registry import (
    ExternalAgentSpec,
    get_external_agent,
    strip_external_prefix,
)
from pahs.external.shell_bridge import run_shell_bridge
from pahs.external.smas_bridge import run_smas
from pahs.storage import db


def run_external_agent(
    agent_name: str,
    command: str,
    *,
    run_id: str | None = None,
) -> dict[str, Any]:
    spec = get_external_agent(agent_name)
    if spec is None:
        raise ValueError(f"External agent `{agent_name}` is not enabled or not found.")

    prompt = strip_external_prefix(command, spec)
    if not prompt:
        prompt = command

    if spec.type == "openclaw":
        result = run_openclaw(spec, prompt)
    elif spec.type == "smas":
        result = run_smas(spec, prompt)
    elif spec.type == "pip":
        result = run_pip(spec, prompt)
    elif spec.type == "shell":
        result = run_shell_bridge(spec, prompt)
    else:
        raise ValueError(f"Unsupported external agent type `{spec.type}`.")

    if run_id:
        db.log_event(
            run_id,
            "external_agent_called",
            {
                "agent_name": agent_name,
                "type": spec.type,
                "ok": result.get("ok"),
                "exit_code": result.get("exit_code"),
                "command_preview": command[:200],
            },
        )
    return result


def format_external_output(agent_name: str, spec: ExternalAgentSpec, result: dict[str, Any]) -> str:
    status = "OK" if result.get("ok") else "ERROR"
    return (
        f"[External Agent: {agent_name}]\n"
        f"Type: {spec.type}\n"
        f"Description: {spec.description}\n"
        f"Status: {status}\n\n"
        f"{result.get('text', '')}"
    )
