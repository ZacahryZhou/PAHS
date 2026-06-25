"""Load YAML config files from the project config directory."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from pahs.paths import PROJECT_ROOT

CONFIG_DIR = PROJECT_ROOT / "config"


@lru_cache
def load_yaml(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / name
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}


def review_policy_for_band(band: str) -> dict[str, Any]:
    policies = load_yaml("review_policy.yaml").get("review_policy", {})
    return dict(policies.get(band, policies.get("simple", {})))


def budget_config() -> dict[str, Any]:
    return load_yaml("budget.yaml")


def models_config() -> dict[str, Any]:
    return load_yaml("models.yaml")


def gateway_config() -> dict[str, Any]:
    return load_yaml("gateway.yaml")


def llm_config() -> dict[str, Any]:
    return load_yaml("llm.yaml")


def external_agents_config() -> dict[str, Any]:
    return load_yaml("external_agents.yaml")
