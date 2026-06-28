"""Telegram bot — /status /best /market /context /history /export /help."""
import asyncio
import io
import structlog
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

from monitor.config import settings
from monitor.scheduler import get_latest_scores, get_last_market, register_alert_callback
from monitor.market import BTC_IMPACT_MESSAGES
from monitor.db import get_score_history, init_db

log = structlog.get_logger()


def _escape(text: str) -> str:
    """Escape MarkdownV2 special chars."""
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


def _format_scores_table(scores: dict, market=None) -> str:
    if not scores:
        return "⏳ No data yet — probe cycle starting\.\.\."

    lines = ["*🤖 AI Sharpness Monitor*\n"]
    for model, data in sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True):
        short = _escape(model)
        score = data["score"]
        emoji = data["emoji"]
        lat = data["latency_ms"]
        lines.append(f"{emoji} *{short}* \u2014 {score}/100 \({lat:.0f}ms\)")
        lines.append(f"   ↳ {_escape(data['recommendation'])}")

    if market and market.ai_load_risk in ("high", "very_high"):
        lines.append("")
        msg = _escape(BTC_IMPACT_MESSAGES[market.ai_load_risk])
        lines.append(f"⚡ *BTC/ETH Alert:* {msg}")
        lines.append(f"   BTC {market.btc_change_1h_pct:+\.2f}% | ETH {market.eth_change_1h_pct:+\.2f}% \(1h\)")

    return "\n".join(lines)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    scores = get_latest_scores()
    market = get_last_market()
    await update.message.reply_text(_format_scores_table(scores, market), parse_mode="MarkdownV2")


async def cmd_best(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    task = " ".join(context.args) if context.args else "general"
    scores = get_latest_scores()
    if not scores:
        await update.message.reply_text("⏳ No data yet \u2014 try in 30s\.", parse_mode="MarkdownV2")
        return
    best_model, best_data = max(scores.items(), key=lambda x: x[1]["score"])
    market = get_last_market()
    lines = [
        f"*Best for: {_escape(task)}*\n",
        f"{best_data['emoji']} *{_escape(best_model)}* \u2014 {best_data['score']}/100",
        f"💬 {_escape(best_data['recommendation'])}",
        f"⚡ Latency: {best_data['latency_ms']:.0f}ms",
    ]
    if market:
        lines.append(f"₿ BTC: \${market.btc_price:,.0f} \({market.btc_change_1h_pct:+\.2f}% 1h\)")
        lines.append(f"Ξ ETH: \${market.eth_price:,.0f} \({market.eth_change_1h_pct:+\.2f}% 1h\)")
        lines.append(f"AI load risk: *{_escape(market.ai_load_risk)}*")
    await update.message.reply_text("\n".join(lines), parse_mode="MarkdownV2")


async def cmd_market(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    market = get_last_market()
    if not market:
        await update.message.reply_text("⏳ Market data not yet fetched\.")
        return
    risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "very_high": "🔴", "unknown": "⚪"}
    lines = [
        "*📊 Crypto Market Context*\n",
        f"₿ BTC: *\${market.btc_price:,.2f}* \| 1h: *{market.btc_change_1h_pct:+\.2f}%* \| Vol: *{_escape(market.btc_volatility_level)}*",
        f"Ξ ETH: *\${market.eth_price:,.2f}* \| 1h: *{market.eth_change_1h_pct:+\.2f}%* \| Vol: *{_escape(market.eth_volatility_level)}*",
        f"Combined: *{_escape(market.volatility_level)}*",
        f"AI load risk: {risk_emoji.get(market.ai_load_risk, '⚪')} *{_escape(market.ai_load_risk)}*",
        f"\n_{_escape(BTC_IMPACT_MESSAGES.get(market.ai_load_risk, ''))}_",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="MarkdownV2")


async def cmd_context(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /context <percentage> \u2014 e\.g\. /context 65", parse_mode="MarkdownV2")
        return
    try:
        pct = float(context.args[0].replace("%", ""))
    except ValueError:
        await update.message.reply_text("Please provide a number, e\.g\. /context 65", parse_mode="MarkdownV2")
        return
    if pct >= 80:
        msg = f"⚠️ Context at {pct:.0f}% \u2014 HIGH degradation risk\. Start a new thread NOW\."
    elif pct >= 60:
        msg = f"⚡ Context at {pct:.0f}% \u2014 degradation risk starting\. Consider resetting soon\."
    elif pct >= 40:
        msg = f"🟡 Context at {pct:.0f}% \u2014 approaching risk zone\."
    else:
        msg = f"✅ Context at {pct:.0f}% \u2014 healthy\."
    await update.message.reply_text(msg, parse_mode="MarkdownV2")


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    model = " ".join(context.args) if context.args else None
    if not model:
        scores = get_latest_scores()
        model = next(iter(scores)) if scores else None
    if not model:
        await update.message.reply_text("No data yet\.", parse_mode="MarkdownV2")
        return
    history = get_score_history(model, hours=24)
    if not history:
        await update.message.reply_text(f"No history for {_escape(model)} yet\.", parse_mode="MarkdownV2")
        return
    scores_list = [h["score"] for h in history]
    avg = sum(scores_list) / len(scores_list)
    trend = "↑" if scores_list[-1] > scores_list[0] else "↓"
    lines = [
        f"*{_escape(model)} \u2014 24h*\n",
        f"Latest: *{scores_list[-1]}/100* {trend}",
        f"Avg: {avg:.1f} \| Min: {min(scores_list)} \| Max: {max(scores_list)}",
        f"Samples: {len(history)}",
    ]
    await update.message.reply_text("\n".join(lines), parse_mode="MarkdownV2")


async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Export score history as CSV file sent directly in Telegram."""
    model = " ".join(context.args) if context.args else None
    if not model:
        scores = get_latest_scores()
        model = next(iter(scores)) if scores else None
    if not model:
        await update.message.reply_text("No data yet\.", parse_mode="MarkdownV2")
        return

    history = get_score_history(model, hours=48)
    if not history:
        await update.message.reply_text(f"No history for {_escape(model)}\.", parse_mode="MarkdownV2")
        return

    import csv as csv_mod
    output = io.StringIO()
    writer = csv_mod.DictWriter(output, fieldnames=history[0].keys())
    writer.writeheader()
    writer.writerows(history)

    filename = f"sharpness_{model.replace('/', '_')}_48h.csv"
    csv_bytes = io.BytesIO(output.getvalue().encode())
    await update.message.reply_document(
        document=csv_bytes,
        filename=filename,
        caption=f"📊 {len(history)} data points for {model} \(48h\)",
        parse_mode="MarkdownV2",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "*🤖 AI Sharpness Monitor*\n\n"
        "/status \u2014 All model scores \+ market\n"
        "/best \[task\] \u2014 Best model right now\n"
        "/market \u2014 BTC \+ ETH volatility & AI load risk\n"
        "/context <pct> \u2014 Context window health\n"
        "/history \[model\] \u2014 24h score trend\n"
        "/export \[model\] \u2014 Download CSV \(48h history\)\n"
        "/help \u2014 This message"
    )
    await update.message.reply_text(text, parse_mode="MarkdownV2")


async def _alert_handler(model: str, old_score: int, new_score: int, data: dict):
    if not settings.telegram_chat_id or not settings.telegram_bot_token:
        return
    try:
        from telegram import Bot
        bot = Bot(token=settings.telegram_bot_token)
        drop = old_score - new_score
        emoji = data.get("emoji", "🔴")
        market_info = ""
        m = data.get("market", {})
        if m.get("ai_load_risk") in ("high", "very_high"):
            market_info = f"\n⚡ BTC {m.get('btc_change_1h_pct', 0):+\.2f}% / ETH signal active"
        msg = (
            f"⚠️ *Score Alert: {_escape(model)}*\n"
            f"{emoji} Dropped {drop} pts: {old_score} → {new_score}\n"
            f"_{_escape(data.get('recommendation', ''))}_"
            f"{market_info}"
        )
        await bot.send_message(chat_id=settings.telegram_chat_id, text=msg, parse_mode="MarkdownV2")
    except Exception as e:
        log.error("telegram_alert_error", error=str(e))


def create_bot() -> Application:
    init_db()
    register_alert_callback(_alert_handler)
    app = Application.builder().token(settings.telegram_bot_token).build()
    for cmd, fn in [
        ("status", cmd_status),
        ("best", cmd_best),
        ("market", cmd_market),
        ("context", cmd_context),
        ("history", cmd_history),
        ("export", cmd_export),
        ("help", cmd_help),
        ("start", cmd_help),
    ]:
        app.add_handler(CommandHandler(cmd, fn))
    return app


if __name__ == "__main__":
    bot = create_bot()
    log.info("telegram_bot_starting")
    bot.run_polling(allowed_updates=Update.ALL_TYPES)
