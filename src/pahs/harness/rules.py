"""Lazy rule loading for the Harness rule layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pahs.paths import PROJECT_ROOT

RULES_DIR = PROJECT_ROOT / "rules"

GLOBAL_RULE_FILES = [
    RULES_DIR / "global" / "safety.md",
    RULES_DIR / "global" / "budget.md",
]

AGENT_RULE_FILES = {
    "orchestrator": RULES_DIR / "agents" / "orchestrator.md",
    "creator": RULES_DIR / "agents" / "creator.md",
    "searcher": RULES_DIR / "agents" / "searcher.md",
}

MODE_RULE_FILES = {
    "DEEP_THINK": RULES_DIR / "modes" / "deep_think.md",
    "CODE": RULES_DIR / "modes" / "code.md",
    "ANALYSIS": RULES_DIR / "modes" / "analysis.md",
}


@dataclass
class RulePack:
    paths: list[str] = field(default_factory=list)
    text: str = ""

    def append_file(self, path: Path) -> None:
        if not path.exists():
            return
        content = path.read_text(encoding="utf-8")
        self.paths.append(str(path.relative_to(PROJECT_ROOT)))
        self.text += f"\n\n# {path.name}\n{content}"


class RuleEngine:
    """Load global rules once, then agent/mode rules only when needed."""

    def load_global(self) -> RulePack:
        pack = RulePack()
        for path in GLOBAL_RULE_FILES:
            pack.append_file(path)
        return pack

    def load_for_agent(self, agent_id: str) -> RulePack:
        pack = RulePack()
        path = AGENT_RULE_FILES.get(agent_id)
        if path:
            pack.append_file(path)
        return pack

    def load_for_mode(self, mode: str) -> RulePack:
        pack = RulePack()
        path = MODE_RULE_FILES.get(mode)
        if path:
            pack.append_file(path)
        return pack
