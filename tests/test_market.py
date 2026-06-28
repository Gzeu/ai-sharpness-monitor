"""Tests for market volatility scoring."""
from monitor.market import volatility_component_score


def test_calm_market():
    assert volatility_component_score(0.3) == 10


def test_moderate_volatility():
    assert volatility_component_score(0.7) == 7


def test_elevated_volatility():
    assert volatility_component_score(1.5) == 4


def test_extreme_volatility():
    assert volatility_component_score(3.0) == 1
