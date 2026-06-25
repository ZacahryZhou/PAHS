"""Load learned plan patterns for Orchestrator (Learner-maintained)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pahs.paths import PROJECT_ROOT

PATTERNS_DIR = PROJECT_ROOT / "standards" / "learned" / "plan_patterns"


def load_plan_patterns() -> list[dict[str, Any]]:
    if not PATTERNS_DIR.exists():
        return []

    patterns: list[dict[str, Any]] = []
    for path in sorted(PATTERNS_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict):
            payload.setdefault("pattern_id", path.stem)
            patterns.append(payload)
    return patterns


def format_patterns_for_prompt(patterns: list[dict[str, Any]]) -> str:
    if not patterns:
        return "(no learned plan patterns yet)"
    lines = ["Learned plan patterns:"]
    for item in patterns:
        lines.append(
            f"- {item.get('pattern_id')}: {item.get('title', '')} — {item.get('summary', '')}"
        )
    return "\n".join(lines)
