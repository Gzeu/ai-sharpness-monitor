"""BTC market volatility — proxy for AI server load spikes.

Logic:
  When BTC moves sharply, a large wave of users rush to AI assistants
  asking about markets, causing load spikes on LLM providers.
  High realized volatility = higher probability of degraded AI responses.

Data source: Binance public REST API via CCXT (no API key required).
"""
import asyncio
import math
import structlog
from datetime import datetime, timezone
from dataclasses import dataclass
from monitor.config import settings

log = structlog.get_logger()


@dataclass
class MarketSnapshot:
    timestamp: datetime
    btc_price: float
    annualized_volatility: float
    price_change_1h_pct: float   # % change in last hour
    price_change_24h_pct: float  # % change in 24h
    volatility_level: str        # calm / moderate / elevated / extreme
    ai_load_risk: str            # low / medium / high / very_high
    component_score: int         # 0-10 for sharpness scorer


def _compute_market_sync(window_minutes: int = 60) -> MarketSnapshot:
    """Fetch BTC OHLCV from Binance public API and compute volatility metrics."""
    try:
        import ccxt
        exchange = ccxt.binance({"enableRateLimit": True})

        # 1-min candles for volatility window
        candles_1m = exchange.fetch_ohlcv("BTC/USDT", timeframe="1m", limit=window_minutes)
        # 1-hour candles for 24h change
        candles_1h = exchange.fetch_ohlcv("BTC/USDT", timeframe="1h", limit=25)

        if not candles_1m or len(candles_1m) < 2:
            raise ValueError("Insufficient candle data")

        closes_1m = [c[4] for c in candles_1m]
        current_price = closes_1m[-1]

        # Realized volatility (annualized)
        returns = [math.log(closes_1m[i] / closes_1m[i - 1]) for i in range(1, len(closes_1m))]
        mean_r = sum(returns) / len(returns)
        variance = sum((r - mean_r) ** 2 for r in returns) / len(returns)
        std = math.sqrt(variance)
        annualized_vol = std * math.sqrt(525600)  # sqrt(minutes per year)

        # 1h price change
        price_1h_ago = closes_1m[0]
        change_1h = ((current_price - price_1h_ago) / price_1h_ago) * 100

        # 24h price change
        change_24h = 0.0
        if candles_1h and len(candles_1h) >= 24:
            price_24h_ago = candles_1h[-25][4] if len(candles_1h) >= 25 else candles_1h[0][4]
            change_24h = ((current_price - price_24h_ago) / price_24h_ago) * 100

        # Classify volatility level
        hi = settings.btc_volatility_high_threshold
        ex = settings.btc_volatility_extreme_threshold
        if annualized_vol < hi * 0.5:
            vol_level = "calm"
        elif annualized_vol < hi:
            vol_level = "moderate"
        elif annualized_vol < ex:
            vol_level = "elevated"
        else:
            vol_level = "extreme"

        # AI load risk: combines volatility + absolute price movement
        abs_change = abs(change_1h)
        if vol_level == "extreme" or abs_change > 3.0:
            ai_load_risk = "very_high"
        elif vol_level == "elevated" or abs_change > 1.5:
            ai_load_risk = "high"
        elif vol_level == "moderate" or abs_change > 0.5:
            ai_load_risk = "medium"
        else:
            ai_load_risk = "low"

        # Component score 0-10 (higher = calmer market = better for AI)
        score_map = {"calm": 10, "moderate": 7, "elevated": 4, "extreme": 1}
        # Further reduce if absolute move is large
        base_score = score_map[vol_level]
        if abs_change > 3.0:
            base_score = max(0, base_score - 3)
        elif abs_change > 1.5:
            base_score = max(0, base_score - 1)

        log.info(
            "market_snapshot",
            btc_price=round(current_price, 2),
            vol=round(annualized_vol, 3),
            vol_level=vol_level,
            change_1h=round(change_1h, 2),
            ai_load_risk=ai_load_risk,
            score=base_score,
        )

        return MarketSnapshot(
            timestamp=datetime.now(timezone.utc),
            btc_price=round(current_price, 2),
            annualized_volatility=round(annualized_vol, 4),
            price_change_1h_pct=round(change_1h, 3),
            price_change_24h_pct=round(change_24h, 3),
            volatility_level=vol_level,
            ai_load_risk=ai_load_risk,
            component_score=base_score,
        )

    except Exception as exc:
        log.warning("market_fetch_failed", error=str(exc))
        # Return neutral snapshot on failure
        return MarketSnapshot(
            timestamp=datetime.now(timezone.utc),
            btc_price=0.0,
            annualized_volatility=0.0,
            price_change_1h_pct=0.0,
            price_change_24h_pct=0.0,
            volatility_level="unknown",
            ai_load_risk="unknown",
            component_score=5,  # neutral fallback
        )


async def get_market_snapshot(window_minutes: int | None = None) -> MarketSnapshot:
    """Async wrapper for sync CCXT call."""
    window = window_minutes or settings.volatility_window_minutes
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _compute_market_sync, window)


BTC_IMPACT_MESSAGES = {
    "low": "BTC calm — AI load risk low",
    "medium": "BTC moderate movement — slight AI load increase possible",
    "high": "⚡ BTC elevated volatility — AI providers likely under higher load",
    "very_high": "🚨 BTC extreme move — AI servers under high load, expect degraded responses",
    "unknown": "Market data unavailable",
}
