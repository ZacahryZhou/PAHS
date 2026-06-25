"""Telegram adapter for PAHS."""

from __future__ import annotations

import os

from pahs.gateway.service import format_pending_lines, handle_inbound_text


def build_telegram_app():
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is missing from environment.")

    from telegram.ext import Application, CommandHandler, MessageHandler, filters

    application = Application.builder().token(token).build()

    async def start(update, context):
        chat_id = str(update.effective_chat.id)
        text = (
            "PAHS Telegram gateway ready.\n\n"
            "Commands:\n"
            "run write a short post about AI\n"
            "reply run_xxx approved\n"
            "pending\n\n"
            f"Chat ID: {chat_id}"
        )
        await update.message.reply_text(text)

    async def on_message(update, context):
        if update.message is None or update.message.text is None:
            return
        chat_id = str(update.effective_chat.id)
        payload = handle_inbound_text(
            update.message.text,
            channel="telegram",
            channel_user_id=chat_id,
        )
        action = payload.get("action")
        if action == "run":
            run_id = payload["run_id"]
            await update.message.reply_text(
                f"Started run: {run_id}\nUse: reply {run_id} approved"
            )
        elif action == "reply":
            run_id = payload["run_id"]
            result = payload["result"]
            if result.get("__interrupt__"):
                await update.message.reply_text(
                    f"Run {run_id} paused again.\nCheck with: pending"
                )
            elif result.get("status") == "COMPLETED":
                await update.message.reply_text(f"Run {run_id} completed.")
            else:
                await update.message.reply_text(f"Run {run_id} updated.")
        elif action == "pending":
            await update.message.reply_text("\n".join(payload["lines"]))
        elif action == "status":
            await update.message.reply_text(str(payload.get("run")))
        else:
            await update.message.reply_text(payload.get("message", "Unknown command."))

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    return application


def run_telegram_bot() -> None:
    app = build_telegram_app()
    app.run_polling()
