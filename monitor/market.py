"""Market volatility proxy — BTC + ETH as dual signal for AI server load spikes.

Logic:
  When BTC or ETH moves sharply, a large wave of users rush to AI assistants
  asking about markets, causing load spikes on LLM providers.
  We compute:
    1. BTC realized volatility (60m window, 1m candles)
    2. ETH realized volatility (same window)
    3. Combined AI load risk from both

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
    # BTC
    btc_price: float
    btc_annualized_volatility: float
    btc_change_1h_pct: float
    btc_change_24h_pct: float
    btc_volatility_level: str
    # ETH
    eth_price: float
    eth_annualized_volatility: float
    eth_change_1h_pct: float
    eth_volatility_level: str
    # Combined
    annualized_volatility: float   # max(BTC, ETH) — for backwards compat
    volatility_level: str          # worst of the two
    ai_load_risk: str              # low / medium / high / very_high
    component_score: int           # 0-10 for sharpness scorer
    # Compat alias
    price_change_1h_pct: float     # = btc_change_1h_pct
    price_change_24h_pct: float    # = btc_change_24h_pct
    btc_price_alias: float = 0.0   # internal


def _fetch_ohlcv(exchange, symbol: str, window_minutes: int) -> tuple[float, float, float, float]:
    """
    Returns (current_price, annualized_vol, change_1h_pct, change_24h_pct).
    Falls back to (0, 0, 0, 0) on error.
    """
    try:
        candles_1m = exchange.fetch_ohlcv(symbol, timeframe="1m", limit=window_minutes)
        candles_1h = exchange.fetch_ohlcv(symbol, timeframe="1h", limit=25)

        if not candles_1m or len(candles_1m) < 2:
            return 0.0, 0.0, 0.0, 0.0

        closes = [c[4] for c in candles_1m]
        price = closes[-1]

        returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
        mean_r = sum(returns) / len(returns)
        variance = sum((r - mean_r) ** 2 for r in returns) / len(returns)
        ann_vol = math.sqrt(variance) * math.sqrt(525600)

        change_1h = ((price - closes[0]) / closes[0]) * 100

        change_24h = 0.0
        if candles_1h and len(candles_1h) >= 2:
            price_24h_ago = candles_1h[0][4]
            change_24h = ((price - price_24h_ago) / price_24h_ago) * 100

        return round(price, 2), round(ann_vol, 4), round(change_1h, 3), round(change_24h, 3)
    except Exception as exc:
        log.warning("ohlcv_fetch_failed", symbol=symbol, error=str(exc))
        return 0.0, 0.0, 0.0, 0.0


def _classify_vol(annualized_vol: float, hi: float, ex: float) -> str:
    if annualized_vol < hi * 0.5:
        return "calm"
    elif annualized_vol < hi:
        return "moderate"
    elif annualized_vol < ex:
        return "elevated"
    elif annualized_vol > 0:
        return "extreme"
    return "unknown"


def _compute_market_sync(window_minutes: int = 60) -> MarketSnapshot:
    try:
        import ccxt
        exchange = ccxt.binance({"enableRateLimit": True})

        hi = settings.btc_volatility_high_threshold
        ex = settings.btc_volatility_extreme_threshold

        btc_price, btc_vol, btc_1h, btc_24h = _fetch_ohlcv(exchange, "BTC/USDT", window_minutes)
        eth_price, eth_vol, eth_1h, _ = _fetch_ohlcv(exchange, "ETH/USDT", window_minutes)

        btc_level = _classify_vol(btc_vol, hi, ex)
        eth_level = _classify_vol(eth_vol, hi, ex)

        # Combined: worst of BTC or ETH
        level_rank = {"unknown": 0, "calm": 1, "moderate": 2, "elevated": 3, "extreme": 4}
        combined_level = max([btc_level, eth_level], key=lambda l: level_rank.get(l, 0))
        combined_vol = max(btc_vol, eth_vol)

        # AI load risk: volatility + absolute 1h moves
        abs_btc = abs(btc_1h)
        abs_eth = abs(eth_1h)
        max_abs_move = max(abs_btc, abs_eth)

        if combined_level == "extreme" or max_abs_move > 3.0:
            ai_risk = "very_high"
        elif combined_level == "elevated" or max_abs_move > 1.5:
            ai_risk = "high"
        elif combined_level == "moderate" or max_abs_move > 0.5:
            ai_risk = "medium"
        else:
            ai_risk = "low"

        # Component score 0-10
        base_map = {"calm": 10, "moderate": 7, "elevated": 4, "extreme": 1, "unknown": 5}
        base_score = base_map[combined_level]
        if max_abs_move > 3.0:
            base_score = max(0, base_score - 3)
        elif max_abs_move > 1.5:
            base_score = max(0, base_score - 1)

        log.info(
            "market_snapshot",
            btc=round(btc_price), btc_vol=round(btc_vol, 3), btc_1h=round(btc_1h, 2),
            eth=round(eth_price), eth_vol=round(eth_vol, 3), eth_1h=round(eth_1h, 2),
            combined_level=combined_level, ai_risk=ai_risk, score=base_score,
        )

        return MarketSnapshot(
            timestamp=datetime.now(timezone.utc),
            btc_price=btc_price,
            btc_annualized_volatility=btc_vol,
            btc_change_1h_pct=btc_1h,
            btc_change_24h_pct=btc_24h,
            btc_volatility_level=btc_level,
            eth_price=eth_price,
            eth_annualized_volatility=eth_vol,
            eth_change_1h_pct=eth_1h,
            eth_volatility_level=eth_level,
            annualized_volatility=combined_vol,
            volatility_level=combined_level,
            ai_load_risk=ai_risk,
            component_score=base_score,
            price_change_1h_pct=btc_1h,
            price_change_24h_pct=btc_24h,
        )

    except Exception as exc:
        log.warning("market_fetch_failed", error=str(exc))
        return MarketSnapshot(
            timestamp=datetime.now(timezone.utc),
            btc_price=0.0, btc_annualized_volatility=0.0,
            btc_change_1h_pct=0.0, btc_change_24h_pct=0.0, btc_volatility_level="unknown",
            eth_price=0.0, eth_annualized_volatility=0.0,
            eth_change_1h_pct=0.0, eth_volatility_level="unknown",
            annualized_volatility=0.0, volatility_level="unknown",
            ai_load_risk="unknown", component_score=5,
            price_change_1h_pct=0.0, price_change_24h_pct=0.0,
        )


async def get_market_snapshot(window_minutes: int | None = None) -> MarketSnapshot:
    window = window_minutes or settings.volatility_window_minutes
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _compute_market_sync, window)


BTC_IMPACT_MESSAGES = {
    "low": "BTC & ETH calm — AI load risk low",
    "medium": "Moderate crypto movement — slight AI load increase possible",
    "high": "⚡ Elevated crypto volatility — AI providers likely under higher load",
    "very_high": "🚨 Extreme crypto move — AI servers under high load, expect degraded responses",
    "unknown": "Market data unavailable",
}
