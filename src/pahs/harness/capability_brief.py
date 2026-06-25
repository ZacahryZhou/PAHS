"""Ground agent answers in the real PAHS project capability surface."""

from __future__ import annotations

import os
import re
from typing import Any

from pahs.external.registry import list_external_agents
from pahs.harness.tools import all_approved_tools
from pahs.planning.capability_catalog import build_capability_catalog, format_catalog_for_prompt
from pahs.providers.router import active_provider_name, llm_status

# Requests that PAHS cannot fully execute with current approved tools.
_GAP_PATTERNS: list[tuple[str, str, str]] = [
    (
        r"开通|注册.{0,8}账号|开户|申请.{0,6}账号|平台账号",
        "platform_account_signup",
        "无法代开通/注册真实平台账号（无浏览器自动化或平台开户 API）",
    ),
    (
        r"管理.{0,6}(账号|号)|代运营|帮我运营|登录.{0,4}(平台|账号)",
        "platform_account_management",
        "无法登录或代运营真实平台账号",
    ),
    (
        r"直接.{0,20}发布|直接发布|发帖到|"
        r"发布到.{0,12}(instagram|ig|youtube|bilibili|tiktok|抖音|小红书|微信|微博)|"
        r"publish to|post to (instagram|youtube|bilibili|tiktok)",
        "direct_social_publish",
        "无法直接向社交平台发帖（除非走 External: SMAS/PIP 做内容，仍需人工发布）",
    ),
    (
        r"付款|支付|绑卡|银行卡|信用卡",
        "payments",
        "无法执行支付或绑定银行卡",
    ),
]

_ALTERNATIVES: dict[str, list[str]] = {
    "platform_account_signup": [
        "Creator：输出分平台注册步骤清单与材料准备表",
        "Searcher：调研最新入驻规则与资质要求",
    ],
    "platform_account_management": [
        "Creator：输出运营 SOP、内容日历、回复话术模板",
        "Searcher：调研竞品账号与热点选题",
        "PIP/SMAS：生成短视频或 IG 图文素材（不代替账号操作）",
    ],
    "direct_social_publish": [
        "SMAS：生成 IG 图文草稿与预览图",
        "PIP：生成短视频成片",
        "Creator：撰写帖子文案与 hashtags",
    ],
    "payments": [
        "Creator：说明人工操作步骤与注意事项",
    ],
}


def _env_flags() -> dict[str, bool]:
    return {
        "deepseek_api_key": bool(os.getenv("DEEPSEEK_API_KEY", "").strip()),
        "perplexity_api_key": bool(os.getenv("PERPLEXITY_API_KEY", "").strip()),
        "tavily_api_key": bool(os.getenv("TAVILY_API_KEY", "").strip()),
        "telegram_bot_token": bool(os.getenv("TELEGRAM_BOT_TOKEN", "").strip()),
    }


def build_capability_snapshot() -> dict[str, Any]:
    """Structured snapshot of what this PAHS install can actually do."""
    tools = all_approved_tools()
    by_worker: dict[str, list[str]] = {}
    for tool in tools.values():
        by_worker.setdefault(tool.agent, []).append(tool.name)

    externals = [
        {
            "name": spec.name,
            "description": spec.description,
            "project_dir": spec.config.get("project_dir"),
        }
        for spec in list_external_agents(enabled_only=True)
    ]

    env = _env_flags()
    search_note = "smart search (Perplexity/Tavily)"
    if not env["perplexity_api_key"] and not env["tavily_api_key"]:
        search_note = "mock search only — set PERPLEXITY_API_KEY or TAVILY_API_KEY"

    return {
        "pipeline": (
            "Path A: ingest → triage → orchestrator → plan → worker → verify → human review"
        ),
        "path_b": "Telegram → intent_router → direct_tools → SMAS/PIP (bypasses orchestrator)",
        "workers": {
            "searcher": {"tools": by_worker.get("searcher", []), "role": "web research + summary"},
            "creator": {"tools": by_worker.get("creator", []), "role": "text deliverables only"},
            "executor": {
                "tools": by_worker.get("executor", []),
                "role": "sandbox Python / files in PAHS data dir",
            },
            "external": {
                "agents": [e["name"] for e in externals],
                "role": "delegate to local SMAS/PIP projects",
            },
        },
        "approved_tools": sorted(tools.keys()),
        "external_agents": externals,
        "llm_provider": active_provider_name(),
        "llm_status": llm_status(),
        "search_mode": search_note,
        "known_limitations": [
            "No browser automation or platform login",
            "No real account signup / credential management",
            "No payment processing",
            "Creator cannot execute actions — only draft text",
            "Executor sandbox is not the public internet",
        ],
    }


def assess_command(command: str) -> dict[str, Any]:
    """Check user request against current capabilities."""
    gaps: list[dict[str, str]] = []
    for pattern, code, message in _GAP_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            gaps.append(
                {
                    "code": code,
                    "message": message,
                    "alternatives": _ALTERNATIVES.get(code, []),
                }
            )

    snapshot = build_capability_snapshot()
    externals = snapshot["external_agents"]
    external_hint = None
    lowered = command.lower()
    if any(k in lowered for k in ("视频", "短视频", "video", "pip")):
        external_hint = "pip"
    elif any(k in lowered for k in ("instagram", "ig", "图文", "smas", "发帖")):
        external_hint = "smas"

    return {
        "command": command[:240],
        "can_fully_execute": not gaps,
        "gaps": gaps,
        "suggested_external": external_hint,
        "available_externals": [e["name"] for e in externals],
        "snapshot_summary": {
            "tools": snapshot["approved_tools"],
            "llm": snapshot["llm_provider"],
            "search": snapshot["search_mode"],
        },
    }


def format_capability_brief_for_prompt(
    command: str,
    *,
    worker: str | None = None,
) -> str:
    """Text block injected into agent system prompts."""
    snapshot = build_capability_snapshot()
    assessment = assess_command(command)
    catalog = build_capability_catalog()

    lines = [
        "=== PAHS Capability Brief (authoritative — do not invent capabilities beyond this) ===",
        f"Pipeline: {snapshot['pipeline']}",
        f"LLM: {snapshot['llm_provider']} | Search: {snapshot['search_mode']}",
        "",
        "Approved tools by worker:",
    ]
    for w, info in snapshot["workers"].items():
        tools = info.get("tools") or info.get("agents") or []
        lines.append(f"- {w}: {info.get('role', '')} | {', '.join(tools) or '—'}")

    if snapshot["external_agents"]:
        lines.append("")
        lines.append("External agents (local projects):")
        for ext in snapshot["external_agents"]:
            proj = ext.get("project_dir") or "configured path"
            lines.append(f"- {ext['name']}: {ext['description']} ({proj})")

    lines.append("")
    lines.append(format_catalog_for_prompt(catalog))

    lines.append("")
    lines.append("Hard limitations:")
    for item in snapshot["known_limitations"]:
        lines.append(f"- {item}")

    if assessment["gaps"]:
        lines.append("")
        lines.append("⚠ This user request exceeds current capabilities:")
        for gap in assessment["gaps"]:
            lines.append(f"- {gap['message']}")
            for alt in gap.get("alternatives") or []:
                lines.append(f"  → Instead: {alt}")

    if assessment.get("suggested_external"):
        name = assessment["suggested_external"]
        if name in assessment.get("available_externals", []):
            lines.append(f"")
            lines.append(
                f"Note: content production may use external agent `{name}` — "
                "still does NOT include account signup or platform login."
            )

    lines.append("")
    lines.append(
        "Response rules: (1) State capability gaps in the first paragraph if any. "
        "(2) Only promise actions listed above. "
        "(3) Offer concrete deliverables PAHS can produce now (checklist, draft, research, SMAS/PIP content)."
    )
    if worker:
        lines.append(f"(You are running as worker: {worker})")
    lines.append("=== End Capability Brief ===")
    return "\n".join(lines)
