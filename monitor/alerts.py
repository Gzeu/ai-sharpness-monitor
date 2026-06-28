"""Alert manager with hysteresis — prevents alert spam on noisy score oscillations.

Hysteresis logic:
  - Alert fires when score drops by >= ALERT_DROP_THRESHOLD points
  - Re-alert only after score recovers by >= RECOVERY_THRESHOLD before dropping again
  - Max 1 alert per model per COOLDOWN_MINUTES window
  - Critical alert (score < CRITICAL_SCORE) always fires, ignoring cooldown
"""
import asyncio
import time
import structlog
from dataclasses import dataclass, field
from typing import Callable, Awaitable

log = structlog.get_logger()

ALERT_DROP_THRESHOLD = 12      # points drop to trigger alert
RECOVERY_THRESHOLD = 8         # points recovered before re-alerting is allowed
COOLDOWN_MINUTES = 30          # minimum minutes between alerts per model
CRITICAL_SCORE = 35            # always alert regardless of cooldown
UPTURN_THRESHOLD = 15          # points gained → "recovery" positive alert


@dataclass
class ModelAlertState:
    last_alerted_at: float = 0.0
    last_alert_score: int = 100
    recovered: bool = True          # True = we can alert on next drop
    high_watermark: int = 0         # highest score since last alert


class AlertManager:
    def __init__(self):
        self._states: dict[str, ModelAlertState] = {}
        self._callbacks: list[Callable] = []

    def register(self, callback: Callable[[str, int, int, dict], Awaitable[None]]):
        self._callbacks.append(callback)

    def _state(self, model: str) -> ModelAlertState:
        if model not in self._states:
            self._states[model] = ModelAlertState()
        return self._states[model]

    async def evaluate(self, model: str, old_score: int, new_score: int, data: dict):
        """Call after each probe cycle. Fires callbacks when alert conditions met."""
        st = self._state(model)
        now = time.time()
        drop = old_score - new_score
        gain = new_score - old_score
        cooldown_elapsed = (now - st.last_alerted_at) > (COOLDOWN_MINUTES * 60)

        # Track recovery high-watermark
        if new_score > st.high_watermark:
            st.high_watermark = new_score

        # Mark as recovered if score climbed enough since last alert
        if new_score >= st.last_alert_score + RECOVERY_THRESHOLD:
            st.recovered = True

        should_alert = False
        alert_type = "drop"

        # 1. Critical: always alert
        if new_score <= CRITICAL_SCORE and old_score > CRITICAL_SCORE:
            should_alert = True
            alert_type = "critical"

        # 2. Drop alert (with hysteresis)
        elif drop >= ALERT_DROP_THRESHOLD and st.recovered and cooldown_elapsed:
            should_alert = True
            alert_type = "drop"

        # 3. Recovery alert (positive)
        elif gain >= UPTURN_THRESHOLD and st.last_alert_score > 0 and cooldown_elapsed:
            should_alert = True
            alert_type = "recovery"

        if should_alert:
            st.last_alerted_at = now
            st.last_alert_score = new_score
            st.recovered = False
            st.high_watermark = new_score
            data["alert_type"] = alert_type
            log.info("alert_fired", model=model, type=alert_type, old=old_score, new=new_score)
            await self._fire(model, old_score, new_score, data)

    async def _fire(self, model, old_score, new_score, data):
        for cb in self._callbacks:
            try:
                await cb(model, old_score, new_score, data)
            except Exception as e:
                log.error("alert_callback_error", error=str(e))


# Singleton
_manager = AlertManager()


def get_alert_manager() -> AlertManager:
    return _manager
