"""Review, approve, and reject staged Builder tools."""

from __future__ import annotations

import shutil

from pahs.builder.tool_manifest import (
    ToolManifest,
    builtin_tool_dir,
    load_manifest,
    load_production_registry,
    manifest_path_for_staging,
    save_manifest,
    save_production_registry,
    staging_tool_dir,
    utc_now,
)
from pahs.storage import db


def review_tool(name: str) -> dict:
    manifest = _require_staging_tool(name)
    tool_dir = staging_tool_dir(name)
    tool_py = (tool_dir / "tool.py").read_text(encoding="utf-8")
    test_py = (tool_dir / "test_tool.py").read_text(encoding="utf-8")
    return {
        "manifest": manifest.to_dict(),
        "tool_py": tool_py,
        "test_tool_py": test_py,
        "callable_by_orchestrator": False,
        "note": "Staging tools are invisible to production orchestration until approved.",
    }


def approve_tool(name: str, *, run_id: str | None = None) -> dict:
    manifest = _require_staging_tool(name)
    if manifest.status == "REJECTED":
        raise ValueError(f"Tool `{name}` was rejected and cannot be approved without a new draft.")
    if manifest.status == "APPROVED":
        raise ValueError(f"Tool `{name}` is already approved.")
    if not manifest.test_passed:
        raise ValueError(f"Tool `{name}` has not passed sandbox tests.")

    src = staging_tool_dir(name)
    dest = builtin_tool_dir(name)
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest)

    manifest.status = "APPROVED"
    manifest.updated_at = utc_now()
    save_manifest(manifest, directory=dest)

    registry = load_production_registry()
    registry[name] = {
        "name": name,
        "description": manifest.description,
        "agent": manifest.agent,
        "status": "APPROVED",
        "module_dir": f"tools/builtin/{name}",
        "function": "run",
        "sandbox": manifest.sandbox,
        "cost_per_call": manifest.cost_per_call,
        "approved_at": manifest.updated_at,
    }
    save_production_registry(registry)
    shutil.rmtree(src)

    if run_id:
        db.log_event(run_id, "builder_tool_approved", {"tool_name": name})
    return {
        "tool_name": name,
        "status": "APPROVED",
        "production_registry": registry[name],
    }


def reject_tool(name: str, *, reason: str, run_id: str | None = None) -> dict:
    manifest = _require_staging_tool(name)
    manifest.status = "REJECTED"
    manifest.reject_reason = reason
    manifest.updated_at = utc_now()
    save_manifest(manifest, directory=staging_tool_dir(name))

    if run_id:
        db.log_event(run_id, "builder_tool_rejected", {"tool_name": name, "reason": reason})
    return {
        "tool_name": name,
        "status": "REJECTED",
        "reason": reason,
    }


def _require_staging_tool(name: str) -> ToolManifest:
    path = manifest_path_for_staging(name)
    if not path.exists():
        raise ValueError(f"Unknown staging tool `{name}`")
    return load_manifest(path)
