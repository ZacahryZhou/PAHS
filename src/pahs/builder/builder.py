"""Mock Builder — generates staged tools and tests."""

from __future__ import annotations

import re
import textwrap

from pahs.builder.sandbox import run_staging_tests
from pahs.builder.tool_manifest import (
    ToolManifest,
    manifest_path_for_staging,
    save_manifest,
    staging_tool_dir,
    utc_now,
)
from pahs.storage import db


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_")
    return slug or "custom_tool"


def _infer_tool_name(requirement: str) -> str:
    lowered = requirement.lower()
    if "word" in lowered and "count" in lowered:
        return "count_words"
    if "upper" in lowered or "大写" in requirement:
        return "to_upper"
    if "timestamp" in lowered or "时间戳" in requirement:
        return "timestamp_now"
    words = requirement.split()[:3]
    return _slugify(" ".join(words) if words else "custom_tool")


def _tool_template(name: str, requirement: str) -> tuple[str, str]:
    if name == "count_words":
        tool_py = textwrap.dedent(
            '''
            """Count words in text."""

            def run(text: str = "") -> dict:
                words = [part for part in text.split() if part.strip()]
                return {"word_count": len(words), "text_preview": text[:80]}
            '''
        ).strip() + "\n"
        test_py = textwrap.dedent(
            '''
            from tool import run

            def test_count_words():
                result = run("hello world from pahs")
                assert result["word_count"] == 4

            if __name__ == "__main__":
                test_count_words()
                print("ok")
            '''
        ).strip() + "\n"
        return tool_py, test_py

    if name == "to_upper":
        tool_py = textwrap.dedent(
            '''
            """Convert text to uppercase."""

            def run(text: str = "") -> dict:
                return {"upper_text": text.upper()}
            '''
        ).strip() + "\n"
        test_py = textwrap.dedent(
            '''
            from tool import run

            def test_to_upper():
                assert run("abc")["upper_text"] == "ABC"

            if __name__ == "__main__":
                test_to_upper()
                print("ok")
            '''
        ).strip() + "\n"
        return tool_py, test_py

    tool_py = textwrap.dedent(
        f'''
        """Generated tool for: {requirement}"""

        def run(text: str = "") -> dict:
            return {{"echo": text, "length": len(text)}}
        '''
    ).strip() + "\n"
    test_py = textwrap.dedent(
        '''
        from tool import run

        def test_echo():
            assert run("pahs")["length"] == 4

        if __name__ == "__main__":
            test_echo()
            print("ok")
        '''
    ).strip() + "\n"
    return tool_py, test_py


def draft_tool(
    requirement: str,
    *,
    agent: str = "executor",
    run_id: str | None = None,
) -> ToolManifest:
    name = _infer_tool_name(requirement)
    tool_dir = staging_tool_dir(name)
    if tool_dir.exists():
        raise ValueError(f"Staging tool `{name}` already exists.")

    now = utc_now()
    manifest = ToolManifest(
        name=name,
        description=requirement.strip(),
        agent=agent,
        status="DRAFT",
        requirement=requirement.strip(),
        created_at=now,
        updated_at=now,
    )
    tool_dir.mkdir(parents=True, exist_ok=True)
    tool_py, test_py = _tool_template(name, requirement)
    (tool_dir / "tool.py").write_text(tool_py, encoding="utf-8")
    (tool_dir / "test_tool.py").write_text(test_py, encoding="utf-8")
    save_manifest(manifest, directory=tool_dir)

    manifest.status = "TESTING"
    manifest.updated_at = utc_now()
    save_manifest(manifest, directory=tool_dir)

    passed, output = run_staging_tests(tool_dir)
    manifest.test_passed = passed
    manifest.test_output = output
    manifest.status = "PENDING_REVIEW" if passed else "DRAFT"
    manifest.updated_at = utc_now()
    save_manifest(manifest, directory=tool_dir)

    if run_id:
        db.log_event(
            run_id,
            "builder_tool_drafted",
            {
                "tool_name": name,
                "status": manifest.status,
                "test_passed": passed,
            },
        )
    return manifest


def get_staging_tool(name: str) -> ToolManifest | None:
    path = manifest_path_for_staging(name)
    if not path.exists():
        return None
    from pahs.builder.tool_manifest import load_manifest

    return load_manifest(path)
