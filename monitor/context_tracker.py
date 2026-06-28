"""Context window health tracker — warns when approaching degradation zone."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# Model context window sizes (tokens)
MODEL_CONTEXT_WINDOWS = {
    "anthropic/claude-sonnet-4-5": 200_000,
    "anthropic/claude-opus-4-5": 200_000,
    "openai/gpt-4o": 128_000,
    "openai/gpt-4o-mini": 128_000,
    "x-ai/grok-2": 131_072,
    "google/gemini-2.0-flash": 1_048_576,
    "meta-llama/llama-3.1-8b-instruct": 131_072,
}

DEGRADATION_THRESHOLD = 0.60  # >60% used → degradation risk
CRITICAL_THRESHOLD = 0.80     # >80% used → high degradation risk


@dataclass
class SessionContext:
    model: str
    session_id: str
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tokens_used: int = 0
    degradation_events: int = 0  # times we noticed quality dropped
    feedback_ratings: list[int] = field(default_factory=list)

    @property
    def context_window(self) -> int:
        return MODEL_CONTEXT_WINDOWS.get(self.model, 100_000)

    @property
    def usage_percent(self) -> float:
        return self.tokens_used / self.context_window

    @property
    def health_status(self) -> str:
        pct = self.usage_percent
        if pct < DEGRADATION_THRESHOLD:
            return "healthy"
        elif pct < CRITICAL_THRESHOLD:
            return "degraded"
        else:
            return "critical"

    def add_tokens(self, count: int) -> None:
        self.tokens_used += count


def context_component_score(session: Optional[SessionContext]) -> int:
    """
    Returns integer 0-15 for the context health component.
    No active session = assume healthy (15 pts).
    """
    if session is None:
        return 15

    pct = session.usage_percent
    if pct < 0.30:
        return 15
    elif pct < 0.50:
        return 12
    elif pct < DEGRADATION_THRESHOLD:
        return 9
    elif pct < CRITICAL_THRESHOLD:
        return 5
    else:
        return 1


def should_warn_context(session: SessionContext) -> tuple[bool, str]:
    """Returns (should_warn, message) if context is approaching degradation."""
    pct = session.usage_percent
    pct_display = round(pct * 100)

    if pct >= CRITICAL_THRESHOLD:
        return True, f"⚠️ Context {pct_display}% — HIGH degradation risk. Recommend starting a new thread."
    elif pct >= DEGRADATION_THRESHOLD:
        return True, f"⚡ Context {pct_display}% — degradation risk starting. Consider resetting soon."
    return False, ""
