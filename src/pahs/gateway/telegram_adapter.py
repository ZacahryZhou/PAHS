"""Telegram adapter for PAHS."""

from __future__ import annotations

import os

from pahs.env import load_project_env
from pahs.gateway.service import format_pending_lines, handle_inbound_text

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
            "PAHS Telegram gateway ready.\n"
            "PAHS Telegram 网关已就绪。\n\n"
            "Start | 启动任务:\n"
            "run write a short post about AI\n"
            "@smas create an IG post for a coffee shop\n"
            "@pip create a 10s promo video\n\n"
            "Review | 审核:\n"
            "reply run_xxx approved\n"
            "pending\n\n"
            f"Chat ID: {chat_id}"
        )
        await update.message.reply_text(text)

    async def on_message(update, context):
        if update.message is None or update.message.text is None:
            return
        chat_id = str(update.effective_chat.id)
        await update.message.reply_text("Working... / 处理中...")
        payload = handle_inbound_text(
            update.message.text,
            channel="telegram",
            channel_user_id=chat_id,
        )
        action = payload.get("action")
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
                proposal_note = ""
                proposals = result.get("learner_proposals") or []
                if proposals:
                    proposal_note = (
                        f"\nLearner proposals: {len(proposals)} pending."
                        f"\nUse CLI: pah proposals pending"
                    )
                await update.message.reply_text(f"Run {run_id} completed.{proposal_note}")
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
