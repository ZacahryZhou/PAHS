"""Helpers for clearing local PAHS test artifacts."""

from __future__ import annotations

import shutil

from pahs.graph.checkpoints import clear_checkpoints
from pahs.harness.budget import BudgetManager
from pahs.learning.proposals import PENDING_DIR, REJECTED_DIR
from pahs.paths import ensure_data_dir
from pahs.storage import db


def clear_learning_pending_files() -> int:
    count = 0
    for folder in (PENDING_DIR, REJECTED_DIR):
        if not folder.exists():
            continue
        for path in folder.glob("*.json"):
            path.unlink()
            count += 1
    return count


def clear_test_outputs() -> int:
    outputs_dir = ensure_data_dir() / "outputs"
    if not outputs_dir.exists():
        return 0
    count = 0
    for path in outputs_dir.iterdir():
        if path.is_file():
            path.unlink()
            count += 1
        elif path.is_dir():
            shutil.rmtree(path)
            count += 1
    return count


def reset_all_test_data(*, include_outputs: bool = True) -> dict:
    summary = db.clear_all_run_data()
    summary["checkpoints_cleared"] = clear_checkpoints()
    summary["output_files_removed"] = clear_test_outputs() if include_outputs else 0
    summary["learning_pending_files_removed"] = clear_learning_pending_files()
    BudgetManager.reset_daily()
    return summary
