"""APScheduler background jobs — runs probing + scoring on a fixed interval."""
import asyncio
import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from monitor.config import settings
from monitor.prober import probe_all_models
from monitor.market import get_btc_volatility, volatility_component_score
from monitor.scorer import compute_sharpness_score

log = structlog.get_logger()

# In-memory state (replace with Redis in production)
_latest_scores: dict = {}
_latency_baselines: dict = {}  # model -> rolling average latency
_error_counts: dict = {}       # model -> list of bools (True=success)


async def run_probe_cycle():
    """Main probe cycle: probe all models, compute scores, store results."""
    log.info("probe_cycle_start")

    btc_vol = await get_btc_volatility()
    vol_score = volatility_component_score(btc_vol)
    log.info("btc_volatility", value=btc_vol, score=vol_score)

    results = await probe_all_models()

    for result in results:
        model = result.model

        # Update error tracking (last 60 probes = ~10 hours at 10min interval)
        if model not in _error_counts:
            _error_counts[model] = []
        _error_counts[model].append(result.success)
        _error_counts[model] = _error_counts[model][-60:]
        recent = _error_counts[model]
        error_rate = 1.0 - (sum(recent) / len(recent)) if recent else 0.0

        # Update rolling baseline (exponential moving average)
        if result.success:
            if model not in _latency_baselines or _latency_baselines[model] <= 0:
                _latency_baselines[model] = result.latency_ms
            else:
                alpha = 0.1  # EMA smoothing factor
                _latency_baselines[model] = (
                    alpha * result.latency_ms + (1 - alpha) * _latency_baselines[model]
                )

        baseline = _latency_baselines.get(model, 0.0)

        score = compute_sharpness_score(
            model=model,
            current_latency_ms=result.latency_ms,
            baseline_latency_ms=baseline,
            probe_success=result.success,
            error_rate_60min=error_rate,
            btc_volatility_score=vol_score,
        )

        _latest_scores[model] = {
            "score": score.total,
            "status": score.status,
            "emoji": score.emoji,
            "recommendation": score.recommendation,
            "breakdown": {
                "time_score": score.time_score,
                "latency_score": score.latency_score,
                "error_rate_score": score.error_rate_score,
                "context_score": score.context_score,
                "volatility_score": score.volatility_score,
                "personal_score": score.personal_score,
            },
            "latency_ms": round(result.latency_ms, 1),
            "latency_vs_baseline_pct": score.latency_vs_baseline_pct,
            "timestamp": score.timestamp.isoformat(),
        }

        log.info(
            "score_computed",
            model=model,
            score=score.total,
            status=score.status,
            latency_ms=round(result.latency_ms),
        )

    log.info("probe_cycle_done", models=len(results))


def get_latest_scores() -> dict:
    return _latest_scores


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        run_probe_cycle,
        trigger=IntervalTrigger(minutes=settings.probe_interval_minutes),
        id="probe_cycle",
        name="Probe all models",
        replace_existing=True,
        misfire_grace_time=60,
    )
    return scheduler
