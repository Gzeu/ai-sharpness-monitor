"""Sharpness scorer — aggregates all signals into a 0-100 score per model."""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from monitor.time_patterns import time_component_score
from monitor.context_tracker import SessionContext, context_component_score

# Score weights (must sum to 100)
WEIGHTS = {
    "time": 25,       # Time of day/week
    "latency": 25,    # Current latency vs baseline
    "error_rate": 15, # Recent error rate
    "context": 15,    # Context window health
    "volatility": 10, # Market volatility proxy
    "personal": 10,   # Personal success rate
}


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
    latency_vs_baseline_pct: float
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
        return {
            "excellent": "Use now — peak conditions",
            "good": "OK, but monitor context usage",
            "degraded": "Expect shorter/generic answers",
            "poor": "Wait 1-2h or switch model",
        }[self.status]


def compute_latency_score(
    current_latency_ms: float,
    baseline_ms: float,
    probe_success: bool,
) -> int:
    """
    Returns 0-25 based on latency vs baseline.
    Failure = 0. >50% above baseline = 0. At baseline = 25.
    """
    if not probe_success or current_latency_ms <= 0:
        return 0
    if baseline_ms <= 0:
        return 20  # No baseline yet — assume neutral

    ratio = current_latency_ms / baseline_ms
    if ratio <= 0.8:
        return 25  # Faster than usual
    elif ratio <= 1.0:
        return 22
    elif ratio <= 1.2:
        return 18
    elif ratio <= 1.5:
        return 12
    elif ratio <= 2.0:
        return 6
    else:
        return 0


def compute_error_rate_score(error_rate: float) -> int:
    """
    Returns 0-15 based on recent error rate (0.0-1.0).
    0% errors = 15. >30% errors = 0.
    """
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
    """
    Returns 0-10 based on personal historical success rate.
    No history = neutral 5.
    """
    if success_rate < 0:
        return 5  # No data
    return round(success_rate * 10)


def compute_sharpness_score(
    model: str,
    current_latency_ms: float,
    baseline_latency_ms: float,
    probe_success: bool,
    error_rate_60min: float,
    btc_volatility_score: int,
    personal_success_rate: float = -1.0,
    session: Optional[SessionContext] = None,
    dt: Optional[datetime] = None,
) -> ScoreBreakdown:
    """Compute full sharpness score for a model."""
    if dt is None:
        dt = datetime.now(timezone.utc)

    t_score = time_component_score(dt)
    l_score = compute_latency_score(current_latency_ms, baseline_latency_ms, probe_success)
    e_score = compute_error_rate_score(error_rate_60min)
    c_score = context_component_score(session)
    v_score = btc_volatility_score
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
        latency_vs_baseline_pct=round(ratio, 1),
        timestamp=dt,
    )
