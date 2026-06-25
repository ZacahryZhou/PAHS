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


def list_recent_runs(*, limit: int = 30) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT run_id, command, status, origin_channel, created_at, updated_at,
                   orchestrator_profile, plan_json
            FROM runs
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    results: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        plan_source = None
        phase_count = 0
        task_count = 0
        primary_worker = None
        if item.get("plan_json"):
            try:
                plan = json.loads(item["plan_json"])
                ep = plan.get("execution_plan") or {}
                plan_source = plan.get("plan_source")
                phases = ep.get("phases") or []
                phase_count = len(phases)
                task_count = sum(len(p.get("tasks") or []) for p in phases)
                if phases and phases[0].get("tasks"):
                    primary_worker = phases[0]["tasks"][0].get("worker")
            except json.JSONDecodeError:
                pass
        item.pop("plan_json", None)
        item.update(
            {
                "plan_source": plan_source,
                "phase_count": phase_count,
                "task_count": task_count,
                "primary_worker": primary_worker,
            }
        )
        results.append(item)
    return results


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


def log_event(run_id: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO run_events (run_id, event_type, payload_json, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                run_id,
                event_type,
                json.dumps(payload or {}, ensure_ascii=False),
                utc_now(),
            ),
        )
        conn.commit()


def list_run_events(run_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM run_events
            WHERE run_id = ?
            ORDER BY id ASC
            """,
            (run_id,),
        ).fetchall()
    results: list[dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        if item.get("payload_json"):
            item["payload"] = json.loads(item["payload_json"])
        results.append(item)
    return results


def register_user_channel(user_id: str, channel: str, channel_user_id: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO user_channels (user_id, channel, channel_user_id)
            VALUES (?, ?, ?)
            """,
            (user_id, channel, channel_user_id),
        )
        conn.commit()


def resolve_user_id(channel: str, channel_user_id: str, *, default: str = "default") -> str:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT user_id FROM user_channels
            WHERE channel = ? AND channel_user_id = ?
            """,
            (channel, channel_user_id),
        ).fetchone()
    if row is None:
        register_user_channel(default, channel, channel_user_id)
        return default
    return str(row["user_id"])


def summarize_test_data() -> dict[str, int]:
    with connect() as conn:
        runs = conn.execute("SELECT COUNT(*) AS c FROM runs").fetchone()["c"]
        pending = conn.execute(
            "SELECT COUNT(*) AS c FROM review_queue WHERE status = 'pending'"
        ).fetchone()["c"]
        reviews = conn.execute("SELECT COUNT(*) AS c FROM review_queue").fetchone()["c"]
        events = conn.execute("SELECT COUNT(*) AS c FROM run_events").fetchone()["c"]
        proposals = conn.execute("SELECT COUNT(*) AS c FROM learning_proposals").fetchone()
        proposal_count = int(proposals["c"]) if proposals else 0
    return {
        "runs": int(runs),
        "pending_reviews": int(pending),
        "review_rows": int(reviews),
        "events": int(events),
        "proposals": proposal_count,
    }


def clear_all_run_data() -> dict[str, int]:
    """Delete all runs, reviews, events, and pending proposals. Keeps user_channels."""
    summary = summarize_test_data()
    with connect() as conn:
        conn.execute("DELETE FROM learning_proposals")
        conn.execute("DELETE FROM run_events")
        conn.execute("DELETE FROM review_queue")
        conn.execute("DELETE FROM runs")
        conn.commit()
    return summary


def insert_proposal(data: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO learning_proposals (
              proposal_id, run_id, proposal_type, status, target_path, title,
              feedback_text, proposed_content, rationale, reject_reason,
              pending_file, created_at, resolved_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["proposal_id"],
                data["run_id"],
                data["proposal_type"],
                data.get("status", "pending"),
                data["target_path"],
                data["title"],
                data["feedback_text"],
                data["proposed_content"],
                data.get("rationale"),
                data.get("reject_reason"),
                data.get("pending_file"),
                data.get("created_at", utc_now()),
                data.get("resolved_at"),
            ),
        )
        conn.commit()


def get_proposal(proposal_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM learning_proposals WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
    return dict(row) if row else None


def list_proposals(*, status: str | None = None) -> list[dict[str, Any]]:
    with connect() as conn:
        if status:
            rows = conn.execute(
                """
                SELECT * FROM learning_proposals
                WHERE status = ?
                ORDER BY created_at ASC
                """,
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM learning_proposals ORDER BY created_at ASC"
            ).fetchall()
    return [dict(row) for row in rows]


def update_proposal_status(
    proposal_id: str,
    *,
    status: str,
    reject_reason: str | None = None,
    pending_file: str | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE learning_proposals
            SET status = ?, reject_reason = ?, pending_file = ?, resolved_at = ?
            WHERE proposal_id = ?
            """,
            (status, reject_reason, pending_file, utc_now(), proposal_id),
        )
        conn.commit()


def count_proposals(*, status: str | None = None) -> int:
    with connect() as conn:
        if status:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM learning_proposals WHERE status = ?",
                (status,),
            ).fetchone()
        else:
            row = conn.execute("SELECT COUNT(*) AS c FROM learning_proposals").fetchone()
    return int(row["c"])
