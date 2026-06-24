"""SQLite helpers for PAHS run and review state."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pahs.paths import ensure_data_dir

SCHEMA_FILE = Path(__file__).with_name("schema.sql")
RUNS_DB = ensure_data_dir() / "runs.db"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(RUNS_DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> Path:
    ensure_data_dir()
    schema = SCHEMA_FILE.read_text(encoding="utf-8")
    with connect() as conn:
        conn.executescript(schema)
        conn.commit()
    return RUNS_DB


def create_run(
    run_id: str,
    command: str,
    *,
    channel: str = "cli",
    user_id: str = "default",
    status: str = "ACTIVE",
) -> None:
    now = utc_now()
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO runs (
              run_id, user_id, status, origin_channel, command, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (run_id, user_id, status, channel, command, now, now),
        )
        conn.commit()


def update_run(
    run_id: str,
    *,
    status: str | None = None,
    orchestrator_profile: str | None = None,
    current_milestone_id: str | None = None,
    plan_json: dict[str, Any] | None = None,
) -> None:
    fields: list[str] = ["updated_at = ?"]
    values: list[Any] = [utc_now()]

    if status is not None:
        fields.append("status = ?")
        values.append(status)
    if orchestrator_profile is not None:
        fields.append("orchestrator_profile = ?")
        values.append(orchestrator_profile)
    if current_milestone_id is not None:
        fields.append("current_milestone_id = ?")
        values.append(current_milestone_id)
    if plan_json is not None:
        fields.append("plan_json = ?")
        values.append(json.dumps(plan_json, ensure_ascii=False))

    values.append(run_id)
    with connect() as conn:
        conn.execute(
            f"UPDATE runs SET {', '.join(fields)} WHERE run_id = ?",
            values,
        )
        conn.commit()


def get_run(run_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return dict(row) if row else None


def enqueue_review(
    run_id: str,
    review_type: str,
    payload: dict[str, Any],
    *,
    milestone_id: str | None = None,
) -> int:
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO review_queue (
              run_id, milestone_id, review_type, payload_json, status, presented_at
            ) VALUES (?, ?, ?, ?, 'pending', ?)
            """,
            (
                run_id,
                milestone_id,
                review_type,
                json.dumps(payload, ensure_ascii=False),
                utc_now(),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def resolve_pending_review(
    run_id: str,
    review_type: str,
    *,
    channel: str = "cli",
) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM review_queue
            WHERE run_id = ? AND review_type = ? AND status = 'pending'
            ORDER BY id DESC
            LIMIT 1
            """,
            (run_id, review_type),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            """
            UPDATE review_queue
            SET status = 'resolved', resolved_at = ?, resolved_via_channel = ?
            WHERE id = ?
            """,
            (utc_now(), channel, row["id"]),
        )
        conn.commit()
        return dict(row)


def list_pending_reviews() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT rq.*, r.command, r.status AS run_status
            FROM review_queue rq
            JOIN runs r ON r.run_id = rq.run_id
            WHERE rq.status = 'pending'
            ORDER BY rq.id ASC
            """
        ).fetchall()
    return [dict(row) for row in rows]
