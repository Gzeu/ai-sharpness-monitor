"""Time-based scoring — off-peak hours and weekends correlate with better LLM performance."""
from datetime import datetime, timezone

# Weights are empirical; adjust based on your observed data
# US East coast business hours (UTC-4) = 13:00-22:00 UTC
# EU business hours (UTC+1/+2) = 07:00-17:00 UTC
# Peak load window approximation: 13:00-22:00 UTC Mon-Fri

PEAK_START_UTC = 13
PEAK_END_UTC = 22


def time_of_day_score(dt: datetime | None = None) -> float:
    """
    Returns a score 0.0-1.0 based on time of day and day of week.
    Higher = better conditions (off-peak).
    """
    if dt is None:
        dt = datetime.now(timezone.utc)

    hour = dt.hour
    weekday = dt.weekday()  # 0=Monday, 6=Sunday
    is_weekend = weekday >= 5

    # Weekend bonus: models tend to perform better on weekends
    if is_weekend:
        base = 0.85
    else:
        base = 0.50

    # Time-of-day adjustment
    if PEAK_START_UTC <= hour < PEAK_END_UTC:
        # Peak hours: penalize
        # Worst at 17:00-19:00 UTC (US+EU overlap)
        overlap_penalty = 0.20 if 17 <= hour < 19 else 0.10
        score = base - overlap_penalty
    elif 0 <= hour < 6:
        # Late night UTC: very low traffic
        score = base + 0.15
    elif 6 <= hour < PEAK_START_UTC:
        # Morning ramp-up
        score = base + 0.05
    else:
        # Post-peak (22:00+)
        score = base + 0.10

    return max(0.0, min(1.0, score))


def time_component_score(dt: datetime | None = None) -> int:
    """Returns integer 0-25 for the time component of sharpness score."""
    return round(time_of_day_score(dt) * 25)
