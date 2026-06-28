"""Tests for the sharpness scorer."""
import pytest
from datetime import datetime, timezone
from monitor.scorer import (
    compute_latency_score,
    compute_error_rate_score,
    compute_personal_score,
    compute_sharpness_score,
)
from monitor.time_patterns import time_component_score


def test_latency_score_below_baseline():
    score = compute_latency_score(800, 1000, True)
    assert score == 25  # Faster than baseline


def test_latency_score_at_baseline():
    score = compute_latency_score(1000, 1000, True)
    assert score == 22


def test_latency_score_20pct_over():
    score = compute_latency_score(1200, 1000, True)
    assert score == 18


def test_latency_score_probe_failed():
    score = compute_latency_score(0, 1000, False)
    assert score == 0


def test_error_rate_zero():
    assert compute_error_rate_score(0.0) == 15


def test_error_rate_high():
    assert compute_error_rate_score(0.5) == 0


def test_personal_score_no_data():
    assert compute_personal_score(-1.0) == 5


def test_personal_score_perfect():
    assert compute_personal_score(1.0) == 10


def test_full_score_excellent():
    # Simulate ideal conditions: off-peak Sunday 3am UTC
    dt = datetime(2026, 6, 28, 3, 0, 0, tzinfo=timezone.utc)  # Sunday
    score = compute_sharpness_score(
        model="anthropic/claude-sonnet-4-5",
        current_latency_ms=900,
        baseline_latency_ms=1000,
        probe_success=True,
        error_rate_60min=0.0,
        btc_volatility_score=10,
        personal_success_rate=0.9,
        dt=dt,
    )
    assert score.total >= 80
    assert score.status == "excellent"


def test_full_score_degraded():
    # Simulate bad conditions: peak hour Monday, high latency
    dt = datetime(2026, 6, 29, 18, 0, 0, tzinfo=timezone.utc)  # Monday peak
    score = compute_sharpness_score(
        model="openai/gpt-4o",
        current_latency_ms=4000,
        baseline_latency_ms=1000,
        probe_success=True,
        error_rate_60min=0.20,
        btc_volatility_score=1,
        personal_success_rate=0.3,
        dt=dt,
    )
    assert score.total < 60
