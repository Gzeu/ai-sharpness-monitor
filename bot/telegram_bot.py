"""Telegram bot interface for AI Sharpness Monitor."""
import asyncio
import structlog
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from monitor.config import settings
from monitor.scheduler import get_latest_scores

log = structlog.get_logger()


def _format_scores_table(scores: dict) -> str:
    if not scores:
        return "⏳ No data yet — probe cycle starting..."

    lines = ["*AI Sharpness Monitor*\n"]
    # Sort by score descending
    sorted_models = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)

    for model, data in sorted_models:
        short_name = model.split("/")[-1]  # Strip provider prefix
        score = data["score"]
        emoji = data["emoji"]
        latency = data["latency_ms"]
        lines.append(f"{emoji} *{short_name}* — {score}/100 ({latency:.0f}ms)")
        lines.append(f"   ↳ {data['recommendation']}")

    return "\n".join(lines)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current scores for all models."""
    scores = get_latest_scores()
    text = _format_scores_table(scores)
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_best(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Recommend best model, optionally for a task type."""
    task = " ".join(context.args) if context.args else "general"
    scores = get_latest_scores()

    if not scores:
        await update.message.reply_text("⏳ No data yet — try again in 30 seconds.")
        return

    best_model, best_data = max(scores.items(), key=lambda x: x[1]["score"])
    short_name = best_model.split("/")[-1]

    text = (
        f"*Best model for: {task}*\n\n"
        f"{best_data['emoji']} *{short_name}* — {best_data['score']}/100\n"
        f"💬 {best_data['recommendation']}\n"
        f"⚡ Latency: {best_data['latency_ms']:.0f}ms"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def cmd_context(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log current context window usage percentage."""
    if not context.args:
        await update.message.reply_text("Usage: /context <percentage> (e.g. /context 65)")
        return

    try:
        pct = float(context.args[0].replace("%", ""))
    except ValueError:
        await update.message.reply_text("Please provide a number, e.g. /context 65")
        return

    if pct >= 80:
        msg = f"⚠️ Context at {pct:.0f}% — HIGH degradation risk. Start a new thread now."
    elif pct >= 60:
        msg = f"⚡ Context at {pct:.0f}% — degradation risk. Consider resetting soon."
    else:
        msg = f"✅ Context at {pct:.0f}% — healthy, no action needed."

    await update.message.reply_text(msg)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "*AI Sharpness Monitor Bot*\n\n"
        "/status — All model scores\n"
        "/best [task] — Best model (optionally for a task)\n"
        "/context <pct> — Check context window health\n"
        "/help — This message"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


def create_bot() -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("best", cmd_best))
    app.add_handler(CommandHandler("context", cmd_context))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))
    return app


if __name__ == "__main__":
    bot = create_bot()
    log.info("telegram_bot_starting")
    bot.run_polling()
