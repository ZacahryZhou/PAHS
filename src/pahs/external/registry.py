"""External agent registry loaded from config."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pahs.config_loader import external_agents_config


@dataclass(frozen=True)
class ExternalAgentSpec:
    name: str
    type: str
    description: str
    config: dict[str, Any]


def _expand_user(path: str) -> str:
    return str(path).replace("~/", f"{__import__('os').path.expanduser('~')}/")


def list_external_agents(*, enabled_only: bool = True) -> list[ExternalAgentSpec]:
    raw = external_agents_config().get("external_agents", {})
    specs: list[ExternalAgentSpec] = []
    for name, item in raw.items():
        if not isinstance(item, dict):
            continue
        if enabled_only and not item.get("enabled", False):
            continue
        specs.append(
            ExternalAgentSpec(
                name=name,
                type=str(item.get("type", "shell")),
                description=str(item.get("description", name)),
                config=item,
            )
        )
    return specs


def get_external_agent(name: str) -> ExternalAgentSpec | None:
    for spec in list_external_agents(enabled_only=False):
        if spec.name == name:
            if not spec.config.get("enabled", False):
                return None
            return spec
    return None


def match_external_agent(command: str) -> ExternalAgentSpec | None:
    lowered = command.lower().strip()
    for spec in list_external_agents(enabled_only=True):
        for prefix in spec.config.get("match_prefixes", []):
            prefix_text = str(prefix).lower()
            if lowered.startswith(prefix_text):
                return spec
        for keyword in spec.config.get("match_keywords", []):
            if str(keyword).lower() in lowered:
                return spec
    return None


def strip_external_prefix(command: str, spec: ExternalAgentSpec) -> str:
    text = command.strip()
    for prefix in spec.config.get("match_prefixes", []):
        prefix_text = str(prefix)
        if text.lower().startswith(prefix_text.lower()):
            return text[len(prefix_text) :].strip()
    for keyword in spec.config.get("match_keywords", []):
        lowered = text.lower()
        key = str(keyword).lower()
        if key in lowered:
            # Remove only the first matched keyword phrase for cleaner prompt.
            idx = lowered.find(key)
            if idx == 0:
                return text[len(key) :].strip(" :，,。")
    return text
