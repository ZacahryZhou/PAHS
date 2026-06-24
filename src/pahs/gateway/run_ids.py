"""Generate stable run identifiers."""

from __future__ import annotations

import secrets
from datetime import datetime


def new_run_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = secrets.token_hex(2)
    return f"run_{stamp}_{suffix}"
