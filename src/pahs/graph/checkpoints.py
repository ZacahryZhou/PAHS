"""LangGraph checkpoint storage."""

from __future__ import annotations

import sqlite3

from langgraph.checkpoint.sqlite import SqliteSaver

from pahs.paths import ensure_data_dir


def get_checkpointer() -> SqliteSaver:
    ensure_data_dir()
    db_path = ensure_data_dir() / "checkpoints.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    return SqliteSaver(conn)
