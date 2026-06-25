"""LangGraph checkpoint storage."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.sqlite import SqliteSaver

from pahs.paths import ensure_data_dir

_CHECKPOINTER: SqliteSaver | None = None


def checkpoint_db_path() -> Path:
    return ensure_data_dir() / "checkpoints.db"


def get_checkpointer() -> SqliteSaver:
    global _CHECKPOINTER
    if _CHECKPOINTER is None:
        db_path = checkpoint_db_path()
        conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL;")
        _CHECKPOINTER = SqliteSaver(conn)
    return _CHECKPOINTER


def clear_checkpoints() -> bool:
    global _CHECKPOINTER
    _CHECKPOINTER = None
    path = checkpoint_db_path()
    if not path.exists():
        return False
    path.unlink()
    wal = path.with_suffix(".db-wal")
    shm = path.with_suffix(".db-shm")
    for extra in (wal, shm):
        if extra.exists():
            extra.unlink()
    return True
