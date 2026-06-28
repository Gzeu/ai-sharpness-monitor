# AI Sharpness Monitor

> Real-time prediction system that tells you **when an LLM is at peak performance** — before you waste a long session on degraded output.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green.svg)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Overview

LLM quality is **not constant**. Server load, context window saturation, and periodic traffic spikes all degrade model output — shorter answers, generic responses, "forgotten" context. This system monitors external + internal signals that correlate with performance and computes a **Sharpness Score (0–100)** per model.

### Sharpness Score Formula

| Signal | Weight | Source |
|---|---|---|
| Time of Day / Week | 25% | Off-peak → higher score |
| API Latency vs baseline | 25% | Live probe every 5–15 min |
| Error Rate (last 60 min) | 15% | OpenRouter / direct API |
| Context Health | 15% | Token count in active session |
| Market Volatility Proxy | 10% | BTC 5m volatility via CCXT |
| Personal Success Rate | 10% | Your historical feedback |

### Score Interpretation

| Score | Status | Recommendation |
|---|---|---|
| 80–100 | 🟢 Excellent | Use now — peak conditions |
| 60–79 | 🟡 Good | Monitor context usage |
| 40–59 | 🟠 Degraded | Expect shorter answers |
| 0–39 | 🔴 Poor | Wait or switch model |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    AI Sharpness Monitor                  │
├──────────────┬──────────────┬──────────────┬────────────┤
│ Latency      │ Market Data  │ Time Pattern │ Context    │
│ Prober       │ (BTC/VIX)    │ Scorer       │ Tracker    │
└──────┬───────┴──────┬───────┴──────┬───────┴────┬───────┘
       │              │              │            │
       └──────────────┴──────────────┴────────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Sharpness Scorer │
                    │   (rules-based)   │
                    └─────────┬─────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
       ┌──────▼──────┐ ┌──────▼──────┐ ┌─────▼──────┐
       │  FastAPI    │ │  Telegram   │ │  Postgres  │
       │  REST API   │ │    Bot      │ │  + Redis   │
       └─────────────┘ └─────────────┘ └────────────┘
```

**Stack:**
- **Backend:** Python 3.11 + FastAPI + APScheduler
- **Cache/Queue:** Redis
- **Storage:** PostgreSQL (metrics history + session logs)
- **Integrations:** OpenRouter API, CCXT (BTC volatility), python-telegram-bot
- **Observability:** Helicone (optional, free tier)

---

## Project Structure

```
ai-sharpness-monitor/
├── monitor/
│   ├── __init__.py
│   ├── config.py           # Settings (env vars)
│   ├── prober.py           # Latency probing per model
│   ├── scorer.py           # Sharpness score computation
│   ├── market.py           # BTC volatility via CCXT
│   ├── time_patterns.py    # Time-of-day/week scoring
│   ├── context_tracker.py  # Context window health
│   └── scheduler.py        # APScheduler background jobs
├── api/
│   ├── __init__.py
│   ├── main.py             # FastAPI app
│   └── routes/
│       ├── scores.py       # GET /scores, GET /scores/{model}
│       ├── sessions.py     # POST /session/feedback
│       └── health.py       # GET /health
├── bot/
│   ├── __init__.py
│   └── telegram_bot.py     # /status, /best, alerts
├── db/
│   ├── models.py           # SQLAlchemy models
│   └── migrations/         # Alembic migrations
├── tests/
│   ├── test_scorer.py
│   ├── test_prober.py
│   └── test_market.py
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── requirements.txt
└── README.md
```

---

## Quick Start

### 1. Clone & Configure

```bash
git clone https://github.com/Gzeu/ai-sharpness-monitor.git
cd ai-sharpness-monitor
cp .env.example .env
# Edit .env with your API keys
```

### 2. Run with Docker

```bash
docker-compose up -d
```

Services start on:
- API: `http://localhost:8000`
- Docs: `http://localhost:8000/docs`

### 3. Manual (dev)

```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn api.main:app --reload
```

---

## API Endpoints

```
GET  /scores                  # All model scores
GET  /scores/{model}          # Single model score + breakdown
GET  /scores/recommend?task=coding   # Best model for a task type
POST /session/start           # Start tracking a session
POST /session/feedback        # Rate a completed session
GET  /health                  # Service health
```

### Example Response

```json
{
  "model": "claude-sonnet-4-5",
  "score": 84,
  "status": "excellent",
  "recommendation": "Use now — peak conditions",
  "breakdown": {
    "time_score": 22,
    "latency_score": 24,
    "error_rate_score": 14,
    "context_health": 12,
    "volatility_proxy": 8,
    "personal_rate": 4
  },
  "latency_ms": 1240,
  "latency_vs_baseline": "-8%",
  "timestamp": "2026-06-28T14:30:00Z"
}
```

---

## Telegram Bot Commands

```
/status          — Show all model scores table
/best            — Recommend best model right now
/best coding     — Best model for a specific task
/context <pct>   — Log context window usage (e.g. /context 65)
/feedback good   — Rate your last session
/history         — Your personal success rates
```

---

## Roadmap

- [x] MVP latency prober
- [x] Sharpness scorer (rules-based)
- [x] Telegram bot
- [ ] PostgreSQL history + trends dashboard
- [ ] Personal ML model (Logistic Regression on session history)
- [ ] Streamlit / web dashboard
- [ ] Context window auto-warning (hook into API responses)
- [ ] OpenTelemetry integration

---

## Cost Estimate

| Component | Cost/month |
|---|---|
| OpenRouter probing (~1K probes/day) | ~$0.50 |
| Railway / Fly.io hosting | ~$5–10 |
| Helicone observability | Free tier |
| **Total** | **~$10–15** |

---

## License

MIT © 2026 George Pricop
