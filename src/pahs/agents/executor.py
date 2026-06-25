"""Executor agent with DEEP_THINK, CODE, and ANALYSIS modes."""

from __future__ import annotations

from pahs.graph.state import PAHSState
from pahs.providers.mock import mock_creator_output
from pahs.tools.registry import call_tool


def executor_node(state: PAHSState) -> dict:
    mode = state.get("execution_mode", "CODE")
    command = state["user_command"]
    feedback = state.get("user_milestone_review", "").strip()

    if mode == "DEEP_THINK":
        output = (
            "[DEEP_THINK Mode]\n"
            f"Task: {command}\n"
            "Plan:\n"
            "1. Clarify goal and constraints\n"
            "2. Break work into reviewable milestones\n"
            "3. Choose the cheapest valid worker for each step\n"
        )
        if feedback:
            output += f"\nRevision requested: {feedback}\n"
        return {"milestone_output": output, "status": "EXECUTED"}

    if mode == "ANALYSIS":
        code = "values = [1, 2, 3, 4, 5]\nprint(sum(values) / len(values))"
        result = call_tool("run_python", code=code)
        output = (
            "[ANALYSIS Mode]\n"
            f"Task: {command}\n"
            f"Python result: {result}\n"
            "Interpretation: computed a simple average as a Week 3 placeholder."
        )
        return {"milestone_output": output, "status": "EXECUTED"}

    # CODE mode
    if any(word in command.lower() for word in ("save", "write", "file", "保存", "文件")):
        path = "outputs/week3_result.txt"
        content = mock_creator_output(command)
        saved = call_tool("write_file", relative_path=path, content=content)
        output = (
            "[CODE Mode]\n"
            f"Task: {command}\n"
            f"Saved file: {saved}\n\n"
            f"{content}"
        )
    else:
        code = "print('CODE mode executed safely in sandbox')"
        result = call_tool("run_python", code=code)
        output = (
            "[CODE Mode]\n"
            f"Task: {command}\n"
            f"Execution: {result}\n"
        )
    if feedback:
        output += f"\nRevision requested: {feedback}"
    return {"milestone_output": output, "status": "EXECUTED"}
