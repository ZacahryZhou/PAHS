"""Bridge to SMAS Instagram post generator."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from pahs.external.registry import ExternalAgentSpec


def clean_smas_prompt(prompt: str) -> str:
    """Remove PAHS meta instructions; keep the actual creative request."""
    text = prompt.strip()
    patterns = [
        r"并且告诉我你调用了什么\s*agent.*$",
        r"告诉我你调用了什么.*$",
        r"what agent.*$",
        r"which agent.*$",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE).strip()
    return text.strip(" ，,。") or prompt.strip()


def _parse_bridge_output(stdout: str, stderr: str, returncode: int) -> dict[str, Any]:
    parsed: dict[str, Any] | None = None
    if stdout:
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError:
            parsed = None

    preview_path = None
    if parsed:
        preview_path = parsed.get("preview_image")

    return {
        "ok": returncode == 0 and bool(parsed),
        "exit_code": returncode,
        "parsed_json": parsed,
        "preview_image": preview_path,
        "raw_stdout": stdout,
        "raw_stderr": stderr,
    }


def _smas_state_path(project_dir: Path) -> Path:
    return project_dir / "state" / "state.json"


def _read_smas_state(project_dir: Path) -> dict[str, Any]:
    path = _smas_state_path(project_dir)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _run_smas_subprocess(
    project_dir: Path,
    bridge: Path,
    cmd: list[str],
    *,
    timeout: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(project_dir),
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def _clear_smas_pending(spec: ExternalAgentSpec, project_dir: Path, bridge: Path, timeout: int) -> None:
    """Drop stale SMAS review/confirm state so a fresh generate can run."""
    state = _read_smas_state(project_dir)
    status = str(state.get("status") or "")
    if status not in {"waiting_review", "confirm_post_type"}:
        return

    if status == "confirm_post_type":
        action = "general"
    else:
        action = "skip"

    _run_smas_subprocess(project_dir, bridge, [str(bridge), "message", action], timeout=timeout)


def run_smas(spec: ExternalAgentSpec, prompt: str) -> dict[str, Any]:
    project_dir = Path(os.path.expanduser(str(spec.config.get("project_dir", "~/Desktop/SMAS"))))
    bridge = project_dir / "scripts" / "smas.sh"
    if not bridge.exists():
        raise RuntimeError(f"SMAS bridge not found: {bridge}")

    cleaned = clean_smas_prompt(prompt)
    subcommand = str(spec.config.get("subcommand", "generate"))
    timeout = int(spec.config.get("timeout_seconds", 900))

    if subcommand == "generate" and bool(spec.config.get("auto_clear_pending", True)):
        _clear_smas_pending(spec, project_dir, bridge, timeout)

    cmd = [str(bridge), subcommand, cleaned]

    result = _run_smas_subprocess(project_dir, bridge, cmd, timeout=timeout)
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    payload = _parse_bridge_output(stdout, stderr, result.returncode)
    payload["command"] = cmd
    payload["external_type"] = "smas"
    payload["external_name"] = spec.name
    return _finalize_smas_payload(project_dir, payload, returncode=result.returncode)


def run_smas_action(spec: ExternalAgentSpec, action_text: str) -> dict[str, Any]:
    """Send approve/edit follow-up to SMAS (uses message routing)."""
    project_dir = Path(os.path.expanduser(str(spec.config.get("project_dir", "~/Desktop/SMAS"))))
    bridge = project_dir / "scripts" / "smas.sh"
    timeout = int(spec.config.get("timeout_seconds", 900))
    cmd = [str(bridge), "message", action_text]

    result = _run_smas_subprocess(project_dir, bridge, cmd, timeout=timeout)
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    payload = _parse_bridge_output(stdout, stderr, result.returncode)
    payload["command"] = cmd
    payload["external_type"] = "smas"
    payload["external_name"] = spec.name
    return _finalize_smas_payload(project_dir, payload, returncode=result.returncode, require_image=False)


def _find_preview_image(project_dir: Path) -> Path | None:
    for name in ("preview_feed.json", "image.json"):
        meta_path = project_dir / "state" / name
        if not meta_path.exists():
            continue
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        file_path = data.get("file")
        if file_path and Path(file_path).exists():
            return Path(file_path)

    for candidate in ("preview_feed.png", "image.png"):
        path = project_dir / "state" / candidate
        if path.exists():
            return path
    return None


def _friendly_smas_error(detail: str) -> str:
    lowered = detail.lower()
    if "validation error" in lowered or "textoverlayline" in lowered:
        return "视觉排版参数格式有误（已自动兼容处理，若仍失败请换个说法再试）"
    if len(detail) > 160:
        return detail[:160].rstrip() + "…"
    return detail


def _smas_failure_message(project_dir: Path, parsed: dict[str, Any] | None) -> str | None:
    state = _read_smas_state(project_dir)
    if state.get("status") == "failed":
        error = _friendly_smas_error(str(state.get("error") or "").strip())
        return f"IG 图文生成失败：{error or '未知错误'}，请稍后再试。"

    raw = str((parsed or {}).get("text") or "").strip()
    if not raw:
        return None
    if "Generation failed" in raw:
        detail = raw.split("Generation failed:", 1)[-1].strip() or "未知错误"
        detail = _friendly_smas_error(detail)
        return f"IG 图文生成失败：{detail}，请稍后再试。"
    if "waiting for review" in raw.lower():
        return "上一条草稿还在审核中，请稍后再试。"
    if "/generate" in raw and "Reply ok / publish" in raw:
        return None
    return None


def _finalize_smas_payload(
    project_dir: Path,
    payload: dict[str, Any],
    *,
    returncode: int,
    require_image: bool = True,
) -> dict[str, Any]:
    parsed = payload.get("parsed_json") or {}
    failure = _smas_failure_message(project_dir, parsed)
    if failure:
        payload["text"] = failure
        payload["ok"] = False
        return payload

    preview = payload.get("preview_image")
    if not preview or not Path(str(preview)).exists():
        state = _read_smas_state(project_dir)
        fallback = _find_preview_image(project_dir)
        if fallback and state.get("status") == "waiting_review":
            payload["preview_image"] = str(fallback)

    payload["text"] = _format_smas_text(project_dir, payload)
    has_image = bool(payload.get("preview_image")) and Path(str(payload["preview_image"])).exists()
    if require_image:
        payload["ok"] = returncode == 0 and has_image
    else:
        payload["ok"] = returncode == 0 and bool(payload.get("text"))
    return payload


def _load_caption(project_dir: Path, parsed: dict[str, Any] | None) -> dict[str, Any]:
    if not parsed:
        return {}
    caption_file = parsed.get("caption_file")
    if caption_file and Path(caption_file).exists():
        return json.loads(Path(caption_file).read_text(encoding="utf-8"))
    fallback = project_dir / "state" / "caption.json"
    if fallback.exists():
        return json.loads(fallback.read_text(encoding="utf-8"))
    return {}


def _format_smas_text(project_dir: Path, payload: dict[str, Any]) -> str:
    parsed = payload.get("parsed_json") or {}
    caption = _load_caption(project_dir, parsed)
    lines: list[str] = []

    if caption.get("hook"):
        lines.append(f"Hook：{caption['hook']}")
    body = caption.get("body") or caption.get("caption") or caption.get("text")
    if body:
        lines.append(str(body).strip())
    hashtags = caption.get("hashtags") or []
    if hashtags:
        lines.append("Hashtags：" + " ".join(str(tag) for tag in hashtags[:8]))

    if not lines:
        raw = str((parsed or {}).get("text") or "").strip()
        if raw and "Reply ok / publish" not in raw and "/generate" not in raw:
            lines.append(raw)
        elif raw:
            lines.append("预览已生成，请看上图。")

    if not lines:
        return "预览已生成，请看上图。"

    return "\n\n".join(lines).strip()
