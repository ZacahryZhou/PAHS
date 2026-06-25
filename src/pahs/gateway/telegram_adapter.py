"""Telegram adapter for PAHS."""

from __future__ import annotations

import os
from pathlib import Path

from pahs.env import load_project_env
from pahs.gateway.intent_router import infer_external_agent
from pahs.gateway.persona import friendly_delivery_intro, friendly_working, normalize_telegram_input
from pahs.gateway.service import handle_inbound_text

load_project_env()


async def _process_message(update, *, raw_text: str) -> None:
    if update.message is None:
        return

    chat_id = str(update.effective_chat.id)
    normalized = normalize_telegram_input(raw_text)
    tool = infer_external_agent(normalized) if normalized != "__help__" else None

    if tool is not None:
        await update.message.reply_text(friendly_working(tool.name))

    payload = handle_inbound_text(
        normalized,
        channel="telegram",
        channel_user_id=chat_id,
        normalized=True,
    )

    action = payload.get("action")

    if action == "deliver":
        agent = str(payload.get("agent_name", "tool"))
        intro = friendly_delivery_intro(agent, awaiting_review=bool(payload.get("awaiting_review")))
        body = f"{intro}\n\n{payload.get('text', '')}"
        image_path = payload.get("image_path")
        if image_path and Path(image_path).is_file():
            with Path(image_path).open("rb") as handle:
                await update.message.reply_photo(photo=handle, caption=body[:1024])
            if len(body) > 1024:
                await update.message.reply_text(body[1024:])
        else:
            await update.message.reply_text(body)
        return

    if action == "chat":
        await update.message.reply_text(str(payload.get("text", "")))
        return

    if action == "run":
        run_id = payload["run_id"]
        command = payload.get("command", "")
        body = f"任务已开始：{run_id}\n内容：{command}"
        interrupt_message = payload.get("interrupt_message")
        if interrupt_message:
            body += f"\n\n{interrupt_message}"
        await update.message.reply_text(body)
    elif action == "reply":
        run_id = payload["run_id"]
        result = payload["result"]
        if result.get("status") == "COMPLETED":
            await update.message.reply_text(f"好了，这个任务已经完成：{run_id}")
        else:
            await update.message.reply_text(f"收到，我继续处理：{run_id}")
    elif action == "pending":
        await update.message.reply_text("\n".join(payload["lines"]))
    elif action == "status":
        await update.message.reply_text(str(payload.get("run")))
    else:
        await update.message.reply_text(str(payload.get("message") or payload.get("text") or "我没听懂，你可以直接说想做什么。"))


def build_telegram_app():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing from environment.")

    from telegram.ext import Application, CommandHandler, MessageHandler, filters

    application = Application.builder().token(token).build()

    async def start(update, context):
        await update.message.reply_text(
            "嗨，我是 PAHS。\n\n"
            "把我当你的主助手就行，直接说需求：\n"
            "• 给咖啡店做一条开业 IG 图文\n"
            "• 做一个 10 秒咖啡宣传短视频\n\n"
            "做好了我直接把结果发给你。"
        )

    async def on_message(update, context):
        if update.message is None or update.message.text is None:
            return
        await _process_message(update, raw_text=update.message.text)

    async def on_command(update, context):
        if update.message is None or update.message.text is None:
            return
        await _process_message(update, raw_text=update.message.text)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", start))
    application.add_handler(CommandHandler("generate", on_command))
    application.add_handler(CommandHandler("video", on_command))
    application.add_handler(MessageHandler(filters.COMMAND, on_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    return application


def run_telegram_bot() -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing. Add it to ~/Desktop/PAHS/.env"
        )
    if ":" not in token or token.count(":") != 1:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN looks incomplete. "
            "It must look like 123456789:AAH... from BotFather (two parts with one colon)."
        )
    try:
        app = build_telegram_app()
        print("PAHS Telegram bot is running. Send messages in Telegram; press Ctrl+C here to stop.")
        print("PAHS Telegram 机器人已启动。在 Telegram 里发消息即可；要停止请按 Ctrl+C。")
        app.run_polling()
    except Exception as exc:
        name = exc.__class__.__name__
        if name == "InvalidToken":
            raise RuntimeError(
                "Telegram rejected TELEGRAM_BOT_TOKEN. "
                "Copy the full token from @BotFather (/token), paste into .env, then retry."
            ) from exc
        raise
