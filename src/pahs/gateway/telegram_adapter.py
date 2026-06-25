"""Telegram adapter for PAHS."""

from __future__ import annotations

import os
from pathlib import Path

from pahs.env import load_project_env
from pahs.gateway.service import handle_inbound_text

load_project_env()


def build_telegram_app():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing from environment.")

    from telegram.ext import Application, CommandHandler, MessageHandler, filters

    application = Application.builder().token(token).build()

    async def start(update, context):
        chat_id = str(update.effective_chat.id)
        text = (
            "PAHS 主控已就绪。\n"
            "PAHS is ready.\n\n"
            "直接说话即可 | Just chat:\n"
            "• 给咖啡店做一条开业 IG 图文 → 自动调用 SMAS\n"
            "• 做一个 10 秒咖啡宣传短视频 → 自动调用 PIP\n"
            "• 普通问题 → PAHS 直接回答\n\n"
            "成果会直接发给你，不用 reply run_id。\n"
            "Results are delivered directly.\n\n"
            f"Chat ID: {chat_id}"
        )
        await update.message.reply_text(text)

    async def on_message(update, context):
        if update.message is None or update.message.text is None:
            return
        chat_id = str(update.effective_chat.id)
        await update.message.reply_text("处理中... / Working...")
        payload = handle_inbound_text(
            update.message.text,
            channel="telegram",
            channel_user_id=chat_id,
        )
        action = payload.get("action")

        if action == "deliver":
            agent = payload.get("agent_name", "tool")
            run_id = payload.get("run_id", "")
            header = f"✅ PAHS → {agent}\nrun_id: {run_id}\n\n"
            body = header + str(payload.get("text", ""))
            image_path = payload.get("image_path")
            if image_path and Path(image_path).is_file():
                with Path(image_path).open("rb") as handle:
                    await update.message.reply_photo(
                        photo=handle,
                        caption=body[:1024],
                    )
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
            body = f"Started run: {run_id}\nCommand: {command}"
            interrupt_message = payload.get("interrupt_message")
            if interrupt_message:
                body += f"\n\n{interrupt_message}"
                body += f"\n\nReply: reply {run_id} approved"
            else:
                body += f"\n\nUse: reply {run_id} approved"
            await update.message.reply_text(body)
        elif action == "reply":
            run_id = payload["run_id"]
            result = payload["result"]
            if result.get("__interrupt__"):
                from pahs.gateway.service import _interrupt_message

                extra = _interrupt_message(result) or ""
                text = f"Run {run_id} paused again.\nCheck: pending"
                if extra:
                    text += f"\n\n{extra}\n\nReply: reply {run_id} <feedback>"
                await update.message.reply_text(text)
            elif result.get("status") == "COMPLETED":
                await update.message.reply_text(f"Run {run_id} completed.")
            else:
                await update.message.reply_text(f"Run {run_id} updated.")
        elif action == "pending":
            from pahs.gateway.service import format_pending_lines

            await update.message.reply_text("\n".join(payload["lines"]))
        elif action == "status":
            await update.message.reply_text(str(payload.get("run")))
        else:
            await update.message.reply_text(payload.get("message", "Unknown command."))

    application.add_handler(CommandHandler("start", start))
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
        app.run_polling()
    except Exception as exc:
        name = exc.__class__.__name__
        if name == "InvalidToken":
            raise RuntimeError(
                "Telegram rejected TELEGRAM_BOT_TOKEN. "
                "Copy the full token from @BotFather (/token), paste into .env, then retry."
            ) from exc
        raise
