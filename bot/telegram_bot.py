"""Telegram bot — /status, /best, /market, /context alerts, /history.

Runs as a separate process alongside the API.
Alerts are registered as callbacks in the scheduler.
"""
import asyncio
import structlog
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from monitor.config import settings
from monitor.scheduler import get_latest_scores, get_last_market, register_alert_callback
from monitor.market import BTC_IMPACT_MESSAGES
from monitor.db import get_score_history, init_db

log = structlog.get_logger()


def _format_scores_table(scores: dict, market=None) -> str:
    if not scores:
        return "⏳ No data yet — probe cycle starting..."

    lines = ["*🤖 AI Sharpness Monitor*\n"]
    sorted_models = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)

    for model, data in sorted_models:
        short_name = model.replace("-instruct", "").replace("-", "\\-")
        score = data["score"]
        emoji = data["emoji"]
        latency = data["latency_ms"]
        lines.append(f"{emoji} *{short_name}* — {score}/100 \\({latency:.0f}ms\\)")
        lines.append(f"   ↳ {data['recommendation']}")

    if market and market.ai_load_risk in ("high", "very_high"):
        lines.append("")
        lines.append(f"⚡ *BTC Alert:* {BTC_IMPACT_MESSAGES[market.ai_load_risk]}")
        lines.append(f"   BTC {market.price_change_1h_pct:+.2f}% \\(1h\\) | Vol: {market.volatility_level}")

    return "\n".join(lines)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    scores = get_latest_scores()
    market = get_last_market()
    text = _format_scores_table(scores, market)
    await update.message.reply_text(text, parse_mode="MarkdownV2")


async def cmd_best(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    task = " ".join(context.args) if context.args else "general"
    scores = get_latest_scores()

    if not scores:
        await update.message.reply_text("⏳ No data yet — try again in 30 seconds.")
        return

    best_model, best_data = max(scores.items(), key=lambda x: x[1]["score"])
    market = get_last_market()

    lines = [
        f"*Best for: {task}*\n",
        f"{best_data['emoji']} *{best_model}* — {best_data['score']}/100",
        f"💬 {best_data['recommendation']}",
        f"⚡ Latency: {best_data['latency_ms']:.0f}ms",
    ]
    if market:
        lines.append(f"₿ BTC: ${market.btc_price:,.0f} \\({market.price_change_1h_pct:+.2f}% 1h\\)")
        lines.append(f"AI load risk: *{market.ai_load_risk}*")

    await update.message.reply_text("\n".join(lines), parse_mode="MarkdownV2")


async def cmd_market(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current BTC market context and its AI load implication."""
    market = get_last_market()
    if not market:
        await update.message.reply_text("⏳ Market data not yet fetched.")
        return

    risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "very_high": "🔴", "unknown": "⚪"}
    lines = [
        "*₿ BTC Market Context*\n",
        f"Price: *${market.btc_price:,.2f}*",
        f"1h change: *{market.price_change_1h_pct:+.2f}%*",
        f"24h change: *{market.price_change_24h_pct:+.2f}%*",
        f"Volatility: *{market.volatility_level}* \\(annualized: {market.annualized_volatility:.3f}\\)",
        f"AI load risk: {risk_emoji.get(market.ai_load_risk, '⚪')} *{market.ai_load_risk}*",
        f"\n_{BTC_IMPACT_MESSAGES.get(market.ai_load_risk, '')}_",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="MarkdownV2")


async def cmd_context(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /context <percentage> — e.g. /context 65")
        return
    try:
        pct = float(context.args[0].replace("%", ""))
    except ValueError:
        await update.message.reply_text("Please provide a number, e.g. /context 65")
        return

    if pct >= 80:
        msg = f"⚠️ Context at {pct:.0f}% — HIGH degradation risk. Start a new thread NOW."
    elif pct >= 60:
        msg = f"⚡ Context at {pct:.0f}% — degradation risk starting. Consider resetting soon."
    elif pct >= 40:
        msg = f"🟡 Context at {pct:.0f}% — watch it, approaching risk zone."
    else:
        msg = f"✅ Context at {pct:.0f}% — healthy, no action needed."

    await update.message.reply_text(msg)


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show score trend for a model over the last 24h."""
    model = " ".join(context.args) if context.args else None
    if not model:
        scores = get_latest_scores()
        if scores:
            model = next(iter(scores))  # default: first model
        else:
            await update.message.reply_text("No data yet.")
            return

    history = get_score_history(model, hours=24)
    if not history:
        await update.message.reply_text(f"No history for {model} yet.")
        return

    # Simple ASCII sparkline
    scores_list = [h["score"] for h in history]
    mini = min(scores_list)
    maxi = max(scores_list)
    avg = sum(scores_list) / len(scores_list)
    latest = scores_list[-1]
    trend = "↑" if len(scores_list) > 1 and scores_list[-1] > scores_list[-2] else "↓"

    lines = [
        f"*{model} — 24h history*\n",
        f"Latest: *{latest}/100* {trend}",
        f"Avg: {avg:.1f} | Min: {mini} | Max: {maxi}",
        f"Samples: {len(history)}",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="MarkdownV2")


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "*AI Sharpness Monitor*\n\n"
        "/status — All model scores \\+ market\n"
        "/best \[task\] — Best model right now\n"
        "/market — BTC volatility \\& AI load risk\n"
        "/context <pct> — Context window health check\n"
        "/history \[model\] — 24h score trend\n"
        "/help — This message"
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")


async def _alert_handler(model: str, old_score: int, new_score: int, data: dict):
    """Called automatically when a model's score drops significantly."""
    if not settings.telegram_chat_id or not settings.telegram_bot_token:
        return
    try:
        from telegram import Bot
        bot = Bot(token=settings.telegram_bot_token)
        drop = old_score - new_score
        emoji = data.get("emoji", "🔴")
        msg = (
            f"⚠️ *Score Alert: {model}*\n"
            f"{emoji} Score dropped {drop} pts: {old_score} → {new_score}\n"
            f"_{data.get('recommendation', '')}_"
        )
        await bot.send_message(chat_id=settings.telegram_chat_id, text=msg, parse_mode="MarkdownV2")
    except Exception as e:
        log.error("telegram_alert_error", error=str(e))


def create_bot() -> Application:
    init_db()
    register_alert_callback(_alert_handler)
    app = Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("best", cmd_best))
    app.add_handler(CommandHandler("market", cmd_market))
    app.add_handler(CommandHandler("context", cmd_context))
    app.add_handler(CommandHandler("history", cmd_history))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("start", cmd_help))
    return app


if __name__ == "__main__":
    bot = create_bot()
    log.info("telegram_bot_starting")
    bot.run_polling(allowed_updates=Update.ALL_TYPES)
