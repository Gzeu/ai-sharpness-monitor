"""Latency prober — uses Cerebras free API (llama-3.3-70b / llama-3.1-8b).

Cerebras is chosen because:
- Free tier with no credit card required
- Extremely fast inference (high tokens/sec) → low latency baseline
- Latency spikes are meaningful signal (Cerebras is usually very fast)
- Models: llama-3.3-70b, llama-3.1-8b
API docs: https://inference-docs.cerebras.ai/
"""
import time
import asyncio
import httpx
import structlog
from datetime import datetime, timezone
from dataclasses import dataclass
from monitor.config import settings

log = structlog.get_logger()

CEREBRAS_API_URL = "https://api.cerebras.ai/v1/chat/completions"

# Fixed probe prompt — short, deterministic, easy to verify
PROBE_PROMPT = "Reply with exactly one word: OK"
PROBE_MAX_TOKENS = 5


@dataclass
class ProbeResult:
    model: str
    timestamp: datetime
    latency_ms: float
    ttft_ms: float | None
    success: bool
    error: str | None = None
    tokens_used: int = 0
    response_text: str = ""


async def probe_model(model: str) -> ProbeResult:
    """Probe a single Cerebras model and return latency metrics."""
    headers = {
        "Authorization": f"Bearer {settings.cerebras_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": PROBE_PROMPT}],
        "max_tokens": PROBE_MAX_TOKENS,
        "temperature": 0,  # deterministic for probing
    }

    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(CEREBRAS_API_URL, headers=headers, json=payload)
            elapsed_ms = (time.perf_counter() - start) * 1000

            if resp.status_code != 200:
                log.warning("probe_failed", model=model, status=resp.status_code, body=resp.text[:200])
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
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

            # Cerebras returns time_info with time_to_first_token
            ttft = None
            if "time_info" in data:
                ttft = data["time_info"].get("time_to_first_token", None)
                if ttft:
                    ttft = ttft * 1000  # convert to ms

            log.info("probe_ok", model=model, latency_ms=round(elapsed_ms), ttft_ms=ttft, tokens=tokens)
            return ProbeResult(
                model=model,
                timestamp=datetime.now(timezone.utc),
                latency_ms=elapsed_ms,
                ttft_ms=ttft,
                success=True,
                tokens_used=tokens,
                response_text=content.strip(),
            )

    except httpx.TimeoutException:
        elapsed_ms = (time.perf_counter() - start) * 1000
        log.error("probe_timeout", model=model)
        return ProbeResult(
            model=model,
            timestamp=datetime.now(timezone.utc),
            latency_ms=elapsed_ms,
            ttft_ms=None,
            success=False,
            error="timeout",
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
