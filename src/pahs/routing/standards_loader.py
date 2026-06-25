"""Load task standards when relevant."""

from __future__ import annotations

from pathlib import Path

from pahs.paths import PROJECT_ROOT

STANDARDS_DIR = PROJECT_ROOT / "standards"

TASK_STANDARD_FILES = {
    "research_report": STANDARDS_DIR / "by_task_type" / "research_report.md",
    "social_post": STANDARDS_DIR / "by_task_type" / "social_post.md",
    "code_task": STANDARDS_DIR / "by_task_type" / "code_task.md",
    "analysis_task": STANDARDS_DIR / "by_task_type" / "code_task.md",
    "general_task": STANDARDS_DIR / "user_preferences.md",
}


def load_standards_for_task(task_type: str) -> dict[str, str]:
    paths: list[str] = []
    texts: list[str] = []

    user_prefs = STANDARDS_DIR / "user_preferences.md"
    if user_prefs.exists():
        paths.append(str(user_prefs.relative_to(PROJECT_ROOT)))
        texts.append(user_prefs.read_text(encoding="utf-8"))

    standard_path = TASK_STANDARD_FILES.get(task_type)
    if standard_path and standard_path.exists():
        rel = str(standard_path.relative_to(PROJECT_ROOT))
        if rel not in paths:
            paths.append(rel)
            texts.append(standard_path.read_text(encoding="utf-8"))

    learned_dir = STANDARDS_DIR / "learned"
    if learned_dir.exists():
        for path in sorted(learned_dir.glob("*.md")):
            rel = str(path.relative_to(PROJECT_ROOT))
            if rel not in paths:
                paths.append(rel)
                texts.append(path.read_text(encoding="utf-8"))

    return {
        "paths": paths,
        "text": "\n\n".join(texts).strip(),
    }
