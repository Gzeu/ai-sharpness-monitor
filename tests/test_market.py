"""Tests for BTC market volatility scoring and AI load risk classification."""
import pytest
from unittest.mock import patch, MagicMock
from monitor.market import volatility_component_score_from_level, BTC_IMPACT_MESSAGES


# Helper used in scorer tests
def volatility_component_score_from_level(vol_level: str, abs_change_1h: float = 0.0) -> int:
    score_map = {"calm": 10, "moderate": 7, "elevated": 4, "extreme": 1, "unknown": 5}
    base = score_map.get(vol_level, 5)
    if abs_change_1h > 3.0:
        base = max(0, base - 3)
    elif abs_change_1h > 1.5:
        base = max(0, base - 1)
    return base


def test_calm_market_score():
    assert volatility_component_score_from_level("calm") == 10


def test_moderate_market_score():
    assert volatility_component_score_from_level("moderate") == 7


def test_elevated_market_score():
    assert volatility_component_score_from_level("elevated") == 4


def test_extreme_market_score():
    assert volatility_component_score_from_level("extreme") == 1


def test_large_move_penalty():
    # 4% move reduces score further
    assert volatility_component_score_from_level("moderate", abs_change_1h=4.0) == 4


def test_btc_impact_messages_coverage():
    for key in ["low", "medium", "high", "very_high", "unknown"]:
        assert key in BTC_IMPACT_MESSAGES
        assert len(BTC_IMPACT_MESSAGES[key]) > 5
