"""Executor agent with DEEP_THINK, CODE, and ANALYSIS modes."""

from __future__ import annotations

from pahs.graph.state import PAHSState
from pahs.planning.task_context import agent_capability_context, effective_task_prompt
from pahs.providers.router import llm_complete
from pahs.tools.registry import call_tool


def executor_node(state: PAHSState) -> dict:
    mode = state.get("execution_mode", "CODE")
    command = effective_task_prompt(state)
    feedback = state.get("user_milestone_review", "").strip()
    model = (state.get("routing_decision") or {}).get("selected_model", "deepseek-chat")
    cap = agent_capability_context(state, worker="executor")

    if mode == "DEEP_THINK":
        output = llm_complete(
            system=cap + "\n\nYou are PAHS Executor in DEEP_THINK mode. Show structured reasoning steps, then the final answer.",
            user=command if not feedback else f"{command}\n\nRevision request: {feedback}",
            model="deepseek-reasoner",
            run_id=state["run_id"],
            phase="deep_think",
        )
        output = "[DEEP_THINK Mode]\n" + output
        return {"milestone_output": output, "status": "EXECUTED"}

    if mode == "ANALYSIS":
        code = "values = [1, 2, 3, 4, 5]\nprint(sum(values) / len(values))"
        result = call_tool("run_python", code=code)
        interpretation = llm_complete(
            system=cap + "\n\nYou are PAHS analysis executor. Interpret the computation briefly.",
            user=f"Task: {command}\nPython result: {result}",
            model=model,
            run_id=state["run_id"],
            phase="analysis",
        )
        output = (
            "[ANALYSIS Mode]\n"
            f"Task: {command}\n"
            f"Python result: {result}\n\n"
            f"{interpretation}"
        )
        return {"milestone_output": output, "status": "EXECUTED"}

    if any(word in command.lower() for word in ("save", "write", "file", "保存", "文件")):
        content = llm_complete(
            system=cap + "\n\nYou are PAHS code executor. Produce file content for the user task.",
            user=command,
            model=model,
            run_id=state["run_id"],
            phase="code",
        )
        path = "outputs/week3_result.txt"
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
        explanation = llm_complete(
            system=cap + "\n\nYou are PAHS code executor. Explain what was done and next steps.",
            user=f"Task: {command}\nSandbox result: {result}",
            model=model,
            run_id=state["run_id"],
            phase="code",
        )
        output = (
            "[CODE Mode]\n"
            f"Task: {command}\n"
            f"Execution: {result}\n\n"
            f"{explanation}"
        )
    if feedback:
        output += f"\nRevision requested: {feedback}"
    return {"milestone_output": output, "status": "EXECUTED"}
