"""Sharpness scorer — aggregates all signals into a 0-100 score per model.

Score weights:
  Time of Day/Week      25pts  — off-peak hours score higher
  Latency vs baseline   25pts  — Cerebras is fast; spikes are meaningful
  Error Rate (60min)    15pts  — recent probe failures
  Context Health        15pts  — token usage in active session
  BTC Volatility Proxy  10pts  — market calm = fewer AI queries
  Personal Success Rate 10pts  — your historical feedback per model
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from monitor.time_patterns import time_component_score
from monitor.context_tracker import SessionContext, context_component_score


@dataclass
class ScoreBreakdown:
    model: str
    total: int
    time_score: int
    latency_score: int
    error_rate_score: int
    context_score: int
    volatility_score: int
    personal_score: int
    latency_ms: float
    ttft_ms: float | None
    latency_vs_baseline_pct: float
    btc_price: float
    btc_change_1h_pct: float
    btc_volatility_level: str
    ai_load_risk: str
    timestamp: datetime

    @property
    def status(self) -> str:
        if self.total >= 80:
            return "excellent"
        elif self.total >= 60:
            return "good"
        elif self.total >= 40:
            return "degraded"
        else:
            return "poor"

    @property
    def emoji(self) -> str:
        return {"excellent": "🟢", "good": "🟡", "degraded": "🟠", "poor": "🔴"}[self.status]

    @property
    def recommendation(self) -> str:
        recs = {
            "excellent": "Use now — peak conditions",
            "good": "OK, but monitor context usage",
            "degraded": "Expect shorter/generic answers",
            "poor": "Wait 1-2h or switch model",
        }
        # Append market warning if relevant
        base = recs[self.status]
        if self.ai_load_risk in ("high", "very_high"):
            base += f" | ⚡ BTC {self.btc_change_1h_pct:+.1f}% (1h) — AI load spike possible"
        return base

    def to_dict(self) -> dict:
        return {
            "score": self.total,
            "status": self.status,
            "emoji": self.emoji,
            "recommendation": self.recommendation,
            "breakdown": {
                "time_score": self.time_score,
                "latency_score": self.latency_score,
                "error_rate_score": self.error_rate_score,
                "context_score": self.context_score,
                "volatility_score": self.volatility_score,
                "personal_score": self.personal_score,
            },
            "latency_ms": round(self.latency_ms, 1),
            "ttft_ms": round(self.ttft_ms, 1) if self.ttft_ms else None,
            "latency_vs_baseline_pct": self.latency_vs_baseline_pct,
            "market": {
                "btc_price": self.btc_price,
                "btc_change_1h_pct": self.btc_change_1h_pct,
                "volatility_level": self.btc_volatility_level,
                "ai_load_risk": self.ai_load_risk,
            },
            "timestamp": self.timestamp.isoformat(),
        }


def compute_latency_score(
    current_latency_ms: float,
    baseline_ms: float,
    probe_success: bool,
) -> int:
    """0-25. Cerebras is fast (~300-800ms typical), so even moderate spikes matter."""
    if not probe_success or current_latency_ms <= 0:
        return 0
    if baseline_ms <= 0:
        return 20  # no baseline yet

    ratio = current_latency_ms / baseline_ms
    if ratio <= 0.8:
        return 25
    elif ratio <= 1.0:
        return 22
    elif ratio <= 1.2:
        return 18
    elif ratio <= 1.5:
        return 12
    elif ratio <= 2.0:
        return 6
    elif ratio <= 3.0:
        return 2
    else:
        return 0


def compute_error_rate_score(error_rate: float) -> int:
    """0-15. Based on fraction of failed probes in the last 60min window."""
    if error_rate <= 0.0:
        return 15
    elif error_rate <= 0.05:
        return 13
    elif error_rate <= 0.10:
        return 10
    elif error_rate <= 0.20:
        return 6
    elif error_rate <= 0.30:
        return 2
    else:
        return 0


def compute_personal_score(success_rate: float) -> int:
    """0-10. Based on personal session feedback history."""
    if success_rate < 0:
        return 5  # no data → neutral
    return round(success_rate * 10)


def compute_sharpness_score(
    model: str,
    current_latency_ms: float,
    baseline_latency_ms: float,
    probe_success: bool,
    error_rate_60min: float,
    market,  # MarketSnapshot
    personal_success_rate: float = -1.0,
    session: Optional[SessionContext] = None,
    dt: Optional[datetime] = None,
) -> ScoreBreakdown:
    """Compute full sharpness score for a model."""
    if dt is None:
        dt = datetime.now(timezone.utc)

    from monitor.time_patterns import time_component_score

    t_score = time_component_score(dt)
    l_score = compute_latency_score(current_latency_ms, baseline_latency_ms, probe_success)
    e_score = compute_error_rate_score(error_rate_60min)
    c_score = context_component_score(session)
    v_score = market.component_score
    p_score = compute_personal_score(personal_success_rate)

    total = t_score + l_score + e_score + c_score + v_score + p_score
    ratio = (current_latency_ms / baseline_latency_ms - 1) * 100 if baseline_latency_ms > 0 else 0.0

    return ScoreBreakdown(
        model=model,
        total=min(100, max(0, total)),
        time_score=t_score,
        latency_score=l_score,
        error_rate_score=e_score,
        context_score=c_score,
        volatility_score=v_score,
        personal_score=p_score,
        latency_ms=current_latency_ms,
        ttft_ms=None,
        latency_vs_baseline_pct=round(ratio, 1),
        btc_price=market.btc_price,
        btc_change_1h_pct=market.price_change_1h_pct,
        btc_volatility_level=market.volatility_level,
        ai_load_risk=market.ai_load_risk,
        timestamp=dt,
    )
