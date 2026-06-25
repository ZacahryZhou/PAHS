"""Detect repeated failures without meaningful progress."""

from __future__ import annotations

import hashlib

from pahs.graph.state import PAHSState


def output_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def detect_no_progress(state: PAHSState) -> tuple[bool, str]:
    retry_count = int(state.get("retry_count", 0))
    current_message = state.get("validation_message", "")
    previous_message = state.get("last_validation_message", "")
    current_hash = output_fingerprint(state.get("milestone_output", ""))
    previous_hash = state.get("last_output_fingerprint", "")

    if retry_count >= 2 and current_message and current_message == previous_message:
        return True, "Same validation failure repeated."

    if retry_count >= 2 and current_hash and current_hash == previous_hash:
        return True, "Worker output did not change after retry."

    return False, ""
