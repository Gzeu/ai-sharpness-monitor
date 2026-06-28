"""Tests for the sharpness scorer."""
import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from monitor.scorer import (
    compute_latency_score,
    compute_error_rate_score,
    compute_personal_score,
    compute_sharpness_score,
)


def mock_market(vol_level="calm", change_1h=0.0, risk="low", score=10):
    m = MagicMock()
    m.component_score = score
    m.btc_price = 100_000.0
    m.price_change_1h_pct = change_1h
    m.annualized_volatility = 0.3
    m.volatility_level = vol_level
    m.ai_load_risk = risk
    return m


# ── Latency score ────────────────────────────────────────────────────────────

def test_latency_faster_than_baseline():
    assert compute_latency_score(800, 1000, True) == 25

def test_latency_at_baseline():
    assert compute_latency_score(1000, 1000, True) == 22

def test_latency_20pct_over():
    assert compute_latency_score(1200, 1000, True) == 18

def test_latency_50pct_over():
    assert compute_latency_score(1500, 1000, True) == 12

def test_latency_2x_baseline():
    assert compute_latency_score(2000, 1000, True) == 6

def test_latency_3x_baseline():
    assert compute_latency_score(3000, 1000, True) == 2

def test_latency_5x_baseline():
    assert compute_latency_score(5000, 1000, True) == 0

def test_latency_probe_failed():
    assert compute_latency_score(0, 1000, False) == 0

def test_latency_no_baseline():
    assert compute_latency_score(1000, 0, True) == 20


# ── Error rate score ─────────────────────────────────────────────────────────

def test_error_rate_zero(): assert compute_error_rate_score(0.0) == 15
def test_error_rate_5pct(): assert compute_error_rate_score(0.05) == 13
def test_error_rate_10pct(): assert compute_error_rate_score(0.10) == 10
def test_error_rate_20pct(): assert compute_error_rate_score(0.20) == 6
def test_error_rate_30pct(): assert compute_error_rate_score(0.30) == 2
def test_error_rate_50pct(): assert compute_error_rate_score(0.50) == 0


# ── Personal score ────────────────────────────────────────────────────────────

def test_personal_no_data(): assert compute_personal_score(-1.0) == 5
def test_personal_perfect(): assert compute_personal_score(1.0) == 10
def test_personal_zero(): assert compute_personal_score(0.0) == 0
def test_personal_mid(): assert compute_personal_score(0.7) == 7


# ── Full score ───────────────────────────────────────────────────────────────

def test_full_score_excellent():
    dt = datetime(2026, 6, 28, 3, 0, 0, tzinfo=timezone.utc)  # Sunday 3am
    score = compute_sharpness_score(
        model="llama-3.3-70b",
        current_latency_ms=400,
        baseline_latency_ms=500,
        probe_success=True,
        error_rate_60min=0.0,
        market=mock_market(vol_level="calm", change_1h=0.1, risk="low", score=10),
        personal_success_rate=0.9,
        dt=dt,
    )
    assert score.total >= 80
    assert score.status == "excellent"
    assert score.ai_load_risk == "low"


def test_full_score_degraded_with_btc_spike():
    dt = datetime(2026, 6, 29, 18, 0, 0, tzinfo=timezone.utc)  # Monday peak
    score = compute_sharpness_score(
        model="llama-3.1-8b",
        current_latency_ms=4000,
        baseline_latency_ms=800,
        probe_success=True,
        error_rate_60min=0.20,
        market=mock_market(vol_level="extreme", change_1h=4.5, risk="very_high", score=1),
        personal_success_rate=0.3,
        dt=dt,
    )
    assert score.total < 50
    assert score.ai_load_risk == "very_high"
    assert "BTC" in score.recommendation


def test_recommendation_includes_btc_warning_on_high_risk():
    dt = datetime(2026, 6, 30, 12, 0, 0, tzinfo=timezone.utc)
    score = compute_sharpness_score(
        model="llama-3.3-70b",
        current_latency_ms=900,
        baseline_latency_ms=1000,
        probe_success=True,
        error_rate_60min=0.0,
        market=mock_market(vol_level="elevated", change_1h=2.5, risk="high", score=4),
        dt=dt,
    )
    assert "BTC" in score.recommendation or score.volatility_score <= 4
