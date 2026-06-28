"""Market volatility proxy — high BTC volatility → more users on AI → possible load spike."""
import asyncio
import structlog
from datetime import datetime, timezone
from monitor.config import settings

log = structlog.get_logger()


def _fetch_btc_volatility_sync(window_minutes: int = 60) -> float:
    """
    Fetch BTC OHLCV data and compute realized volatility over the window.
    Returns annualized volatility as a float (e.g. 0.85 = 85%).
    Falls back to 0.0 on any error.
    """
    try:
        import ccxt
        exchange = ccxt.binance({"enableRateLimit": True})
        # 1-minute candles, fetch enough for the window
        candles = exchange.fetch_ohlcv("BTC/USDT", timeframe="1m", limit=window_minutes)
        closes = [c[4] for c in candles]  # close prices
        if len(closes) < 2:
            return 0.0

        import math
        returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        std = math.sqrt(variance)
        # Annualize: sqrt(525600 minutes/year)
        annualized = std * math.sqrt(525600)
        return round(annualized, 4)
    except Exception as exc:
        log.warning("btc_volatility_fetch_failed", error=str(exc))
        return 0.0


async def get_btc_volatility(window_minutes: int | None = None) -> float:
    """Async wrapper — runs sync CCXT call in executor."""
    window = window_minutes or settings.volatility_window_minutes
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _fetch_btc_volatility_sync, window)


def volatility_component_score(annualized_vol: float) -> int:
    """
    Returns integer 0-10 for the volatility component of sharpness score.
    Lower volatility → higher score (calmer market = fewer AI queries about crypto).
    """
    # Thresholds based on typical BTC annualized vol ranges:
    # <0.5  = calm        → full 10 pts
    # 0.5-1.0 = moderate  → 7 pts
    # 1.0-2.0 = elevated  → 4 pts
    # >2.0  = extreme     → 1 pt
    if annualized_vol < 0.5:
        return 10
    elif annualized_vol < 1.0:
        return 7
    elif annualized_vol < 2.0:
        return 4
    else:
        return 1
