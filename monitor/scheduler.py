"""APScheduler background jobs — probe cycle + in-memory state.

No Redis needed. State lives in-memory; SQLite persists history.
On restart, baselines are rebuilt after a few probe cycles.
"""
import asyncio
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime, timezone

from monitor.config import settings
from monitor.prober import probe_all_models
from monitor.market import get_market_snapshot, BTC_IMPACT_MESSAGES
from monitor.scorer import compute_sharpness_score
from monitor.db import save_probe_log, save_sharpness_score

log = structlog.get_logger()

# ── In-memory state (replaces Redis) ──────────────────────────────────────────
_latest_scores: dict = {}
_latency_baselines: dict = {}   # model -> EMA latency (ms)
_error_window: dict = {}        # model -> list[bool] (True=success), last 60
_last_market = None             # cached MarketSnapshot
_alert_callbacks: list = []     # registered alert handlers


def register_alert_callback(fn):
    """Register a coroutine to be called when a score drops significantly."""
    _alert_callbacks.append(fn)


def get_latest_scores() -> dict:
    return _latest_scores


def get_last_market():
    return _last_market


async def _fire_alerts(model: str, old_score: int, new_score: int, data: dict):
    """Fire registered alert callbacks when score drops significantly."""
    drop = old_score - new_score
    if drop >= settings.alert_score_drop_threshold:
        for cb in _alert_callbacks:
            try:
                await cb(model=model, old_score=old_score, new_score=new_score, data=data)
            except Exception as e:
                log.error("alert_callback_error", error=str(e))


async def run_probe_cycle():
    """Main probe cycle: probe all models, fetch market data, compute scores."""
    global _last_market
    log.info("probe_cycle_start")

    # 1. Fetch market snapshot (BTC volatility)
    market = await get_market_snapshot()
    _last_market = market

    if market.ai_load_risk in ("high", "very_high"):
        log.warning(
            "btc_ai_load_warning",
            risk=market.ai_load_risk,
            btc_change_1h=market.price_change_1h_pct,
            vol_level=market.volatility_level,
            msg=BTC_IMPACT_MESSAGES[market.ai_load_risk],
        )

    # 2. Probe all models
    results = await probe_all_models()

    for result in results:
        model = result.model

        # Update error window (last 60 probes ≈ 15h at 15min interval)
        if model not in _error_window:
            _error_window[model] = []
        _error_window[model].append(result.success)
        _error_window[model] = _error_window[model][-60:]

        recent = _error_window[model]
        error_rate = 1.0 - (sum(recent) / len(recent)) if recent else 0.0

        # Update EMA baseline (only on successful probes)
        if result.success and result.latency_ms > 0:
            if model not in _latency_baselines:
                _latency_baselines[model] = result.latency_ms
            else:
                alpha = 0.1
                _latency_baselines[model] = (
                    alpha * result.latency_ms + (1 - alpha) * _latency_baselines[model]
                )

        baseline = _latency_baselines.get(model, 0.0)

        # 3. Compute sharpness score
        score = compute_sharpness_score(
            model=model,
            current_latency_ms=result.latency_ms,
            baseline_latency_ms=baseline,
            probe_success=result.success,
            error_rate_60min=error_rate,
            market=market,
        )

        score_dict = score.to_dict()

        # 4. Fire alerts if score dropped
        old_score = _latest_scores.get(model, {}).get("score", score.total)
        await _fire_alerts(model, old_score, score.total, score_dict)

        _latest_scores[model] = score_dict

        # 5. Persist to SQLite
        await save_probe_log(result)
        await save_sharpness_score(score, market.annualized_volatility)

        log.info(
            "score_computed",
            model=model,
            score=score.total,
            status=score.status,
            latency_ms=round(result.latency_ms),
            btc_risk=market.ai_load_risk,
        )

    log.info("probe_cycle_done", models=len(results), btc_price=market.btc_price)


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_probe_cycle,
        trigger=IntervalTrigger(minutes=settings.probe_interval_minutes),
        id="probe_cycle",
        name="Probe all models + market snapshot",
        replace_existing=True,
        misfire_grace_time=120,
    )
    return scheduler
