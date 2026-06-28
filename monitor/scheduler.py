"""Background scheduler — probe every 15 min, maintain EMA baselines, fire alerts."""
import asyncio
import time
from datetime import datetime, timezone
from typing import Callable, Awaitable, Optional

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from monitor.config import settings
from monitor.prober import probe_model
from monitor.scorer import compute_score
from monitor.market import get_market_snapshot, MarketSnapshot
from monitor.alerts import get_alert_manager
from monitor.db import save_probe_log, save_score

log = structlog.get_logger()

# In-memory state
_latest_scores: dict = {}
_last_market: Optional[MarketSnapshot] = None
_latency_ema: dict[str, float] = {}       # EMA per model
_error_counts: dict[str, list] = {}       # rolling timestamps of errors
_alert_callbacks: list[Callable] = []    # legacy compat

EMA_ALPHA = 0.1
ERROR_WINDOW_SECONDS = 3600


def get_latest_scores() -> dict:
    return _latest_scores.copy()


def get_last_market() -> Optional[MarketSnapshot]:
    return _last_market


def register_alert_callback(cb: Callable[[str, int, int, dict], Awaitable[None]]):
    """Register a callback for score drop alerts (legacy compat + bot)."""
    get_alert_manager().register(cb)
    _alert_callbacks.append(cb)  # keep ref


def _update_ema(model: str, latency_ms: float) -> float:
    prev = _latency_ema.get(model, latency_ms)
    new_ema = EMA_ALPHA * latency_ms + (1 - EMA_ALPHA) * prev
    _latency_ema[model] = new_ema
    return new_ema


def _record_error(model: str, is_error: bool):
    now = time.time()
    if model not in _error_counts:
        _error_counts[model] = []
    if is_error:
        _error_counts[model].append(now)
    # prune old
    _error_counts[model] = [t for t in _error_counts[model] if now - t < ERROR_WINDOW_SECONDS]


def _error_rate(model: str) -> float:
    """Errors per hour in the last 60 min window."""
    return len(_error_counts.get(model, []))


async def run_probe_cycle():
    global _last_market

    log.info("probe_cycle_start", models=settings.models_to_probe)

    # Fetch market data once per cycle
    try:
        _last_market = await get_market_snapshot()
        log.info(
            "market_fetched",
            btc=round(_last_market.btc_price),
            eth=round(_last_market.eth_price),
            risk=_last_market.ai_load_risk,
        )
    except Exception as e:
        log.warning("market_fetch_error", error=str(e))

    alert_mgr = get_alert_manager()

    for model in settings.models_to_probe:
        try:
            probe = await probe_model(model)
            _record_error(model, probe.error is not None)
            ema_latency = _update_ema(model, probe.latency_ms if not probe.error else 9999)

            score_data = compute_score(
                model=model,
                latency_ms=probe.latency_ms,
                ema_latency_ms=ema_latency,
                error_count=_error_rate(model),
                market=_last_market,
                context_pct=0.0,  # updated per-session via /session endpoints
            )

            old_score = _latest_scores.get(model, {}).get("score", score_data["score"])

            _latest_scores[model] = {
                **score_data,
                "latency_ms": probe.latency_ms,
                "ema_latency_ms": round(ema_latency, 1),
                "probed_at": datetime.now(timezone.utc).isoformat(),
                "error": probe.error,
            }

            # Persist to SQLite
            save_probe_log(
                model=model,
                latency_ms=probe.latency_ms,
                error=probe.error,
                score=score_data["score"],
                btc_change_1h=_last_market.btc_change_1h_pct if _last_market else 0.0,
                eth_change_1h=_last_market.eth_change_1h_pct if _last_market else 0.0,
                ai_load_risk=_last_market.ai_load_risk if _last_market else "unknown",
            )

            # Alert evaluation (hysteresis managed in AlertManager)
            await alert_mgr.evaluate(
                model=model,
                old_score=old_score,
                new_score=score_data["score"],
                data={**score_data, "latency_ms": probe.latency_ms, "market": {
                    "btc_change_1h_pct": _last_market.btc_change_1h_pct if _last_market else 0,
                    "eth_change_1h_pct": _last_market.eth_change_1h_pct if _last_market else 0,
                    "ai_load_risk": _last_market.ai_load_risk if _last_market else "unknown",
                }},
            )

            log.info(
                "probe_ok",
                model=model,
                score=score_data["score"],
                latency=round(probe.latency_ms),
                status=score_data["status"],
            )

        except Exception as e:
            log.error("probe_cycle_model_error", model=model, error=str(e))

    log.info("probe_cycle_done", models_scored=len(_latest_scores))


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        run_probe_cycle,
        trigger="interval",
        minutes=settings.probe_interval_minutes,
        id="probe_cycle",
        replace_existing=True,
        max_instances=1,
    )
    return scheduler
