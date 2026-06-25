"""Natural-language replies for Telegram."""

from __future__ import annotations

import re

PAHS_PERSONA_SYSTEM = """你是 PAHS，用户私人主助手。像真人助理一样说话：自然、简短、有温度。
规则：
- 用用户同样的语言回复（中文问就中文答）。
- 不要堆砌技术命令，不要提 run_id、reply approved，除非用户明确问技术细节。
- 你能帮用户：IG/图文内容（后台自动用 SMAS）、短视频（后台自动用 PIP）、一般问答。
- 如果用户要产出内容，鼓励他用自然语言直接说需求，例如「给咖啡店做一条开业 IG 图文」。
- 每次回复控制在 2-4 句，除非用户要详细说明。"""


_QUICK_REPLIES: list[tuple[list[str], str]] = [
    (
        ["在吗", "在不在", "hello", "hi", "hey"],
        "在的，我在这儿。你要是做 IG 图文或短视频，直接跟我说需求就行。",
    ),
    (
        ["看得到", "能看到", "看见我的", "收到吗", "听得到", "可以看到", "看到我的", "我的信息", "我的消息"],
        "看得到，你发的我都收到了。想让我帮你做什么？",
    ),
    (
        ["你是谁", "你是什么", "what are you"],
        "我是 PAHS，你的主助手。你跟我说需求，我会自动帮你调对应工具完成任务。",
    ),
    (
        ["怎么用", "如何使用", "help"],
        "就像跟朋友说话一样就行。比如：\n「给咖啡店做一条开业 IG 图文」\n「做一个 10 秒咖啡宣传短视频」",
    ),
]


def normalize_telegram_input(text: str) -> str:
    stripped = text.strip()
    lowered = stripped.lower()

    if lowered.startswith("/generate"):
        rest = stripped.split(maxsplit=1)[1] if len(stripped.split(maxsplit=1)) > 1 else ""
        return f"做一条 IG 图文：{rest}".strip(" ：:") if rest else "做一条 IG 图文"

    if lowered.startswith("/video"):
        rest = stripped.split(maxsplit=1)[1] if len(stripped.split(maxsplit=1)) > 1 else ""
        return f"做一个短视频：{rest}".strip(" ：:") if rest else "做一个 10 秒宣传短视频"

    if lowered in {"/help", "/start"}:
        return "__help__"

    if lowered.startswith("/"):
        # Unknown slash command -> pass through as chat question.
        return stripped.lstrip("/").replace("_", " ")

    return stripped


def quick_reply(text: str) -> str | None:
    lowered = text.lower().strip()
    for needles, answer in _QUICK_REPLIES:
        if any(needle in lowered or needle in text for needle in needles):
            return answer
    return None


def friendly_help() -> str:
    return (
        "嗨，我是 PAHS。\n\n"
        "你直接跟我说想做什么就行，例如：\n"
        "• 给咖啡店做一条开业 IG 图文\n"
        "• 做一个 10 秒咖啡宣传短视频\n\n"
        "做好了我直接把结果发给你。"
    )


def friendly_working(tool_name: str | None = None) -> str:
    if tool_name == "smas":
        return "好，我先帮你做 IG 图文，可能要一两分钟，稍等～"
    if tool_name == "pip":
        return "好，我开始做短视频了，这个会久一点，稍等～"
    return "好，我处理一下，稍等～"


def friendly_delivery_intro(agent_name: str, *, awaiting_review: bool = False) -> str:
    if agent_name == "smas" and awaiting_review:
        return "预览图来了（SMAS），你看下这版："
    if agent_name == "smas":
        return "这是最终版本："
    if agent_name == "pip":
        return "视频任务结果："
    return "结果如下："


def strip_robotic_prefix(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^\[Mock Creator Output\]\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^Task:\s*.+\n", "", cleaned, count=1)
    return cleaned.strip()
