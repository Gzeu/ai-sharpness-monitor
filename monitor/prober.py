"""Latency prober — sends a fixed probe prompt to each model and records TTFT + total latency."""
import time
import asyncio
import httpx
import structlog
from datetime import datetime, timezone
from dataclasses import dataclass
from monitor.config import settings

log = structlog.get_logger()

PROBE_PROMPT = "Reply with exactly: OK"
PROBE_MAX_TOKENS = 5


@dataclass
class ProbeResult:
    model: str
    timestamp: datetime
    latency_ms: float
    ttft_ms: float | None  # time to first token (streaming)
    success: bool
    error: str | None = None
    tokens_used: int = 0


async def probe_model(model: str) -> ProbeResult:
    """Probe a single model via OpenRouter and return latency metrics."""
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/Gzeu/ai-sharpness-monitor",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROBE_PROMPT}],
        "max_tokens": PROBE_MAX_TOKENS,
        "stream": False,
    }

    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            elapsed_ms = (time.perf_counter() - start) * 1000

            if resp.status_code != 200:
                log.warning("probe_failed", model=model, status=resp.status_code)
                return ProbeResult(
                    model=model,
                    timestamp=datetime.now(timezone.utc),
                    latency_ms=elapsed_ms,
                    ttft_ms=None,
                    success=False,
                    error=f"HTTP {resp.status_code}",
                )

            data = resp.json()
            tokens = data.get("usage", {}).get("total_tokens", 0)
            log.info("probe_ok", model=model, latency_ms=round(elapsed_ms), tokens=tokens)
            return ProbeResult(
                model=model,
                timestamp=datetime.now(timezone.utc),
                latency_ms=elapsed_ms,
                ttft_ms=None,  # streaming TTFT requires stream=True — add in Phase 2
                success=True,
                tokens_used=tokens,
            )
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        log.error("probe_exception", model=model, error=str(exc))
        return ProbeResult(
            model=model,
            timestamp=datetime.now(timezone.utc),
            latency_ms=elapsed_ms,
            ttft_ms=None,
            success=False,
            error=str(exc),
        )


async def probe_all_models() -> list[ProbeResult]:
    """Probe all configured models concurrently."""
    tasks = [probe_model(m) for m in settings.model_list]
    results = await asyncio.gather(*tasks)
    return list(results)
