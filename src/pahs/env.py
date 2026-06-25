"""Load project .env for local development."""

from __future__ import annotations

from pahs.paths import PROJECT_ROOT


def load_project_env() -> None:
    env_file = PROJECT_ROOT / ".env"
    if not env_file.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_file, override=False)
