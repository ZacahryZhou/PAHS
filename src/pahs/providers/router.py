"""Select mock or DeepSeek and record usage."""

from __future__ import annotations

import os
from typing import Any

from pahs.config_loader import llm_config
from pahs.providers.deepseek import DeepSeekProvider
from pahs.providers.mock import mock_creator_output, mock_plan, mock_triage
from pahs.storage import db

_deepseek = DeepSeekProvider()


def active_provider_name() -> str:
    cfg = llm_config().get("llm", {}).get("provider", "auto")
    if cfg == "mock":
        return "mock"
    if cfg == "deepseek":
        return "deepseek" if _deepseek.available else "mock"
    return "deepseek" if _deepseek.available else "mock"


def llm_status() -> dict[str, Any]:
    return {
        "configured_provider": llm_config().get("llm", {}).get("provider", "auto"),
        "active_provider": active_provider_name(),
        "deepseek_api_key_set": _deepseek.available,
        "deepseek_chat_model": _deepseek.chat_model,
        "deepseek_reasoner_model": _deepseek.reasoner_model,
    }


def _record_usage(run_id: str | None, phase: str, result: dict[str, Any]) -> None:
    if not run_id:
        return
    usage = result.get("usage") or {}
    db.log_event(
        run_id,
        "llm_usage",
        {
            "phase": phase,
            "provider": result.get("provider", "unknown"),
            "model": result.get("model"),
            "usage": usage,
        },
    )


def llm_complete(
    *,
    system: str,
    user: str,
    model: str | None = None,
    run_id: str | None = None,
    phase: str = "complete",
) -> str:
    if active_provider_name() == "deepseek":
        try:
            result = _deepseek.complete(system=system, user=user, model=model)
            _record_usage(run_id, phase, result)
            return str(result["content"]).strip()
        except Exception as exc:
            if os.getenv("PAHS_LLM_STRICT", "").lower() in {"1", "true", "yes"}:
                raise
            fallback = mock_creator_output(user)
            if run_id:
                db.log_event(
                    run_id,
                    "llm_fallback",
                    {"phase": phase, "error": str(exc), "provider": "mock"},
                )
            return fallback

    if phase == "triage":
        return str(mock_triage(user))
    if phase == "plan":
        return str(mock_plan(user, "lite", mock_triage(user)))
    return mock_creator_output(user)


def triage_with_llm(command: str, *, run_id: str | None = None) -> dict[str, Any]:
    base = mock_triage(command)
    if active_provider_name() != "deepseek":
        return base

    system = (
        "You are PAHS Triage. Return ONLY compact JSON with keys: "
        "complexity_score, complexity_band, needs_research, needs_code, "
        "needs_deep_reasoning, recommended_orchestrator, task_type."
    )
    try:
        text = llm_complete(
            system=system,
            user=f"Classify this command: {command}",
            model=_deepseek.chat_model,
            run_id=run_id,
            phase="triage",
        )
        import json

        parsed = json.loads(text.strip().strip("`").removeprefix("json"))
        base.update({k: v for k, v in parsed.items() if k in base or k in parsed})
        base["recommended_orchestrator"] = parsed.get(
            "recommended_orchestrator", base["recommended_orchestrator"]
        )
        base["llm_enhanced"] = True
    except Exception:
        base["llm_enhanced"] = False
    return base
