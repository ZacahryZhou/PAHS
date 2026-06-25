"""FastAPI dev server for PAHS Dev Lab."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pahs.devlab.architecture_map import build_progress
from pahs.devlab.run_manager import get_handle, resume_run_async, run_snapshot, start_run_async
from pahs.storage import db

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="PAHS Dev Lab", version="0.1.0")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ReplyRequest(BaseModel):
    message: str = Field(min_length=1)


@app.on_event("startup")
def _startup() -> None:
    db.init_db()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/chat")
def post_chat(body: ChatRequest) -> dict[str, Any]:
    handle = start_run_async(body.message.strip())
    return {
        "run_id": handle.run_id,
        "status": handle.status,
        "command": handle.command,
    }


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, Any]:
    snapshot = run_snapshot(run_id)
    if snapshot.get("error") == "not_found":
        raise HTTPException(status_code=404, detail="Run not found")
    return snapshot


@app.get("/api/runs/{run_id}/progress")
def get_progress(run_id: str) -> dict[str, Any]:
    snapshot = run_snapshot(run_id)
    if snapshot.get("error") == "not_found":
        raise HTTPException(status_code=404, detail="Run not found")
    events = db.list_run_events(run_id)
    progress = build_progress(
        events,
        run_status=str(snapshot.get("status") or ""),
        waiting_review=bool(snapshot.get("waiting_review")),
    )
    return {"run_id": run_id, **progress, "snapshot": snapshot}


@app.get("/api/runs/{run_id}/events")
def list_events(run_id: str) -> dict[str, Any]:
    if db.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return {"run_id": run_id, "events": db.list_run_events(run_id)}


@app.post("/api/runs/{run_id}/reply")
def post_reply(run_id: str, body: ReplyRequest) -> dict[str, Any]:
    if db.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")
    handle = resume_run_async(run_id, body.message.strip())
    return {
        "run_id": run_id,
        "status": handle.status,
        "accepted": True,
    }


@app.get("/api/runs/{run_id}/events/stream")
async def stream_events(run_id: str, after_id: int = 0) -> StreamingResponse:
    if db.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator():
        cursor = after_id
        idle_ticks = 0
        while idle_ticks < 120:
            events = db.list_run_events(run_id)
            new_events = [event for event in events if int(event.get("id", 0)) > cursor]
            snapshot = run_snapshot(run_id)
            progress = build_progress(
                events,
                run_status=str(snapshot.get("status") or ""),
                waiting_review=bool(snapshot.get("waiting_review")),
            )

            if new_events or idle_ticks == 0:
                payload = {
                    "events": new_events,
                    "progress": progress,
                    "snapshot": snapshot,
                }
                if new_events:
                    cursor = int(new_events[-1]["id"])
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
                idle_ticks = 0
            else:
                idle_ticks += 1

            terminal = snapshot.get("status") in {
                "COMPLETED",
                "FAILED",
                "BLOCKED",
            }
            waiting = bool(snapshot.get("waiting_review"))
            if terminal and not waiting:
                break
            if waiting:
                idle_ticks = 0
            await asyncio.sleep(0.4)

        yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def run_server(*, host: str = "127.0.0.1", port: int = 8765) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port, log_level="info")
