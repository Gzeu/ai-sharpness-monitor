"""Tests for context window health tracking."""
from monitor.context_tracker import (
    SessionContext,
    context_component_score,
    should_warn_context,
    DEGRADATION_THRESHOLD,
    CRITICAL_THRESHOLD,
)


def make_session(model: str = "llama-3.3-70b", tokens: int = 0) -> SessionContext:
    s = SessionContext(model=model, session_id="test-001")
    s.tokens_used = tokens
    return s


def test_healthy_session_max_score():
    s = make_session(tokens=10_000)  # very low usage
    assert context_component_score(s) == 15


def test_none_session_returns_max():
    assert context_component_score(None) == 15


def test_degradation_zone_score_reduced():
    # llama-3.3-70b has 131_072 window
    # 60% = ~78_643 tokens
    s = make_session("llama-3.3-70b", tokens=80_000)
    score = context_component_score(s)
    assert score <= 9  # in degradation zone


def test_critical_zone_score_minimal():
    s = make_session("llama-3.3-70b", tokens=110_000)  # > 80%
    score = context_component_score(s)
    assert score <= 5


def test_no_warn_below_threshold():
    s = make_session(tokens=50_000)
    warn, msg = should_warn_context(s)
    assert not warn
    assert msg == ""


def test_warn_at_degradation_threshold():
    s = make_session("llama-3.3-70b", tokens=82_000)  # ~62%
    warn, msg = should_warn_context(s)
    assert warn
    assert "degradation" in msg.lower()


def test_warn_critical():
    s = make_session("llama-3.3-70b", tokens=112_000)  # ~85%
    warn, msg = should_warn_context(s)
    assert warn
    assert "HIGH" in msg or "new thread" in msg.lower()


def test_usage_percent_calculation():
    s = make_session("openai/gpt-4o", tokens=64_000)  # 50% of 128K
    assert abs(s.usage_percent - 0.5) < 0.01
