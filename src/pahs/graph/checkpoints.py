"""LangGraph checkpoint storage."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from pahs.paths import ensure_data_dir


def checkpoint_db_path() -> Path:
    return ensure_data_dir() / "checkpoints.db"


def get_checkpointer() -> SqliteSaver:
    db_path = checkpoint_db_path()
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    return SqliteSaver(conn)


def clear_checkpoints() -> bool:
    path = checkpoint_db_path()
    if not path.exists():
        return False
    path.unlink()
    return True
