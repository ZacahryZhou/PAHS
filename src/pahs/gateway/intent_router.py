"""Natural-language routing to external tools."""

from __future__ import annotations

from pahs.external.registry import ExternalAgentSpec, list_external_agents, match_external_agent

# Extra intent rules (checked before generic keyword match).
INTENT_RULES: list[tuple[str, list[str]]] = [
    (
        "pip",
        [
            "短视频",
            "生成视频",
            "做个视频",
            "做一个视频",
            "视频宣传",
            "promo video",
            "short video",
            "10秒",
            "15秒",
            "30秒",
        ],
    ),
    (
        "smas",
        [
            "ig图文",
            "ig 图文",
            "ins图文",
            "ins 图文",
            "instagram",
            "ins post",
            "ig post",
            "发ins",
            "发 ig",
            "发帖",
            "图文",
            "小红书",
            "social post",
            "instagram post",
            "做一个帖子",
            "做一条图文",
        ],
    ),
]


def infer_external_agent(text: str) -> ExternalAgentSpec | None:
    """Pick a tool from natural language, not only @smas / @pip."""
    explicit = match_external_agent(text)
    if explicit is not None:
        return explicit

    lowered = text.lower().strip()
    enabled = {spec.name: spec for spec in list_external_agents(enabled_only=True)}

    for agent_name, phrases in INTENT_RULES:
        if agent_name not in enabled:
            continue
        for phrase in phrases:
            if phrase.lower() in lowered or phrase in text:
                return enabled[agent_name]

    return None
