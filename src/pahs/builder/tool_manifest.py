"""Tool manifest schema and lifecycle helpers."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pahs.paths import PROJECT_ROOT

TOOLS_DIR = PROJECT_ROOT / "tools"
STAGING_DIR = TOOLS_DIR / "staging"
BUILTIN_DIR = TOOLS_DIR / "builtin"
PRODUCTION_REGISTRY = BUILTIN_DIR / "production_registry.json"

ToolStatus = Literal[
    "DRAFT",
    "TESTING",
    "PENDING_REVIEW",
    "APPROVED",
    "REJECTED",
    "DEPRECATED",
]


@dataclass
class ToolManifest:
    name: str
    description: str
    agent: str
    status: ToolStatus
    requirement: str
    created_at: str
    updated_at: str
    test_passed: bool = False
    test_output: str = ""
    reject_reason: str | None = None
    sandbox: bool = True
    cost_per_call: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ToolManifest":
        return cls(**data)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def staging_tool_dir(name: str) -> Path:
    return STAGING_DIR / name


def builtin_tool_dir(name: str) -> Path:
    return BUILTIN_DIR / name


def manifest_path_for_staging(name: str) -> Path:
    return staging_tool_dir(name) / "manifest.json"


def load_manifest(path: Path) -> ToolManifest:
    data = json.loads(path.read_text(encoding="utf-8"))
    return ToolManifest.from_dict(data)


def save_manifest(manifest: ToolManifest, *, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "manifest.json"
    path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def list_staging_manifests() -> list[ToolManifest]:
    manifests: list[ToolManifest] = []
    if not STAGING_DIR.exists():
        return manifests
    for folder in sorted(STAGING_DIR.iterdir()):
        manifest_file = folder / "manifest.json"
        if manifest_file.exists():
            manifests.append(load_manifest(manifest_file))
    return manifests


def load_production_registry() -> dict[str, dict[str, Any]]:
    if not PRODUCTION_REGISTRY.exists():
        return {}
    return json.loads(PRODUCTION_REGISTRY.read_text(encoding="utf-8"))


def save_production_registry(registry: dict[str, dict[str, Any]]) -> None:
    BUILTIN_DIR.mkdir(parents=True, exist_ok=True)
    PRODUCTION_REGISTRY.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
