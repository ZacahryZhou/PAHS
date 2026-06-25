"""Telegram per-chat session for tool review follow-ups."""

from __future__ import annotations

import json
from typing import Any

from pahs.paths import ensure_data_dir

SESSION_FILE = ensure_data_dir() / "telegram_sessions.json"


def _load() -> dict[str, Any]:
    if not SESSION_FILE.exists():
        return {}
    return json.loads(SESSION_FILE.read_text(encoding="utf-8"))


def _save(data: dict[str, Any]) -> None:
    SESSION_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def set_smas_review(chat_id: str, *, run_id: str, image_path: str | None = None) -> None:
    data = _load()
    data[chat_id] = {
        "tool": "smas",
        "run_id": run_id,
        "image_path": image_path,
        "status": "awaiting_review",
    }
    _save(data)


def get_session(chat_id: str) -> dict[str, Any] | None:
    return _load().get(chat_id)


def clear_session(chat_id: str) -> None:
    data = _load()
    if chat_id in data:
        del data[chat_id]
        _save(data)


def is_smas_review_reply(text: str) -> bool:
    lowered = text.strip().lower()
    if lowered in {"好", "ok", "yes", "通过", "可以", "满意"}:
        return True
    return text.strip().startswith(("改：", "改:", "edit:", "edit "))


def parse_smas_review_reply(text: str) -> tuple[str, str]:
    """Return (action, payload) where action is approve|edit."""
    stripped = text.strip()
    lowered = stripped.lower()
    if lowered in {"好", "ok", "yes", "通过", "可以", "满意"}:
        return "approve", stripped
    if stripped.startswith("改："):
        return "edit", stripped.split("改：", 1)[1].strip()
    if stripped.startswith("改:"):
        return "edit", stripped.split("改:", 1)[1].strip()
    if lowered.startswith("edit:"):
        return "edit", stripped.split(":", 1)[1].strip()
    if lowered.startswith("edit "):
        return "edit", stripped[5:].strip()
    return "approve", stripped
