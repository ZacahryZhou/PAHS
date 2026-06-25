"""Simple file helpers restricted to the PAHS data directory."""

from __future__ import annotations

from pathlib import Path

from pahs.paths import ensure_data_dir

DATA_DIR = ensure_data_dir()


def _safe_path(relative_path: str) -> Path:
    target = (DATA_DIR / relative_path).resolve()
    if DATA_DIR.resolve() not in target.parents and target != DATA_DIR.resolve():
        raise ValueError("Path escapes PAHS data directory.")
    return target


def read_file(relative_path: str) -> str:
    return _safe_path(relative_path).read_text(encoding="utf-8")


def write_file(relative_path: str, content: str) -> str:
    target = _safe_path(relative_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return str(target)
