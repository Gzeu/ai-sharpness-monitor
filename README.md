# AI Sharpness Monitor

> Predict and alert in real-time when an LLM is at peak performance — before wasting a long session on degraded output.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green.svg)](https://fastapi.tiangolo.com)
[![Cost](https://img.shields.io/badge/Cost-$0%2Fmonth-brightgreen.svg)](#cost)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Why this exists

LLM quality is **not constant**. The same model gives dramatically different responses depending on:

- **Server load** (peak US/EU business hours → degraded responses)
- **Context window saturation** (>60% used → model "forgets" earlier context)
- **BTC/crypto volatility** — when BTC moves sharply, a wave of users ask AI about markets → load spike on all providers

This system monitors all three signals and computes a **Sharpness Score (0–100)** per model in real-time.

---

## Sharpness Score Formula

| Signal | Weight | Notes |
|---|---|---|
| Time of Day / Week | 25pts | Off-peak hours, weekends score higher |
| API Latency vs baseline | 25pts | Cerebras is fast — spikes are meaningful |
| Error Rate (last 60min) | 15pts | Recent probe failures |
| Context Window Health | 15pts | % of context used in active session |
| BTC Volatility Proxy | 10pts | High vol = more AI queries = more load |
| Personal Success Rate | 10pts | Your historical session feedback |

### Score → Action

| Score | Status | Action |
|---|---|---|
| 80–100 | 🟢 Excellent | Use now — peak conditions |
| 60–79 | 🟡 Good | OK, monitor context |
| 40–59 | 🟠 Degraded | Expect shorter/generic answers |
| 0–39 | 🔴 Poor | Wait 1-2h or switch model |

---

## Stack — 100% Free, 100% Local

| Component | Solution | Cost |
|---|---|---|
| LLM probe API | [Cerebras free tier](https://cloud.cerebras.ai) — llama-3.3-70b | **$0** |
| Database | SQLite (local file `./data/sharpness.db`) | **$0** |
| Cache | In-memory Python dict | **$0** |
| Market data | Binance public REST API via CCXT (no key needed) | **$0** |
| Hosting | Runs locally — `python run.py` | **$0** |
| Observability | Structured logs via `structlog` | **$0** |
| **Total** | | **$0/month** |

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                AI Sharpness Monitor                  │
├──────────────┬───────────────┬──────────────┬────────┤
│ Prober       │ Market (BTC)  │ Time Pattern │ Context│
│ Cerebras API │ Binance CCXT  │ Scorer       │ Tracker│
└──────┬───────┴───────┬───────┴──────┬───────┴────┬───┘
       └───────────────┴──────────────┴────────────┘
                              │
                   ┌──────────▼──────────┐
                   │  Sharpness Scorer   │
                   │  (rules-based)      │
                   └──────────┬──────────┘
                              │
             ┌────────────────┼────────────────┐
             │                │                │
      ┌──────▼──────┐  ┌──────▼──────┐  ┌─────▼──────┐
      │  FastAPI    │  │  Telegram   │  │  SQLite    │
      │  :8000      │  │    Bot      │  │  ./data/   │
      └─────────────┘  └─────────────┘  └────────────┘
```

**BTC → AI Load logic:**
When BTC moves sharply (>1.5% in 1h or high annualized volatility), the system marks `ai_load_risk = high/very_high` and reduces the volatility component score, adding a warning to every recommendation.

---

## Quick Start

### Prerequisites

- Python 3.11+
- [Cerebras free API key](https://cloud.cerebras.ai) (free, no credit card)
- Telegram bot token (optional, via [@BotFather](https://t.me/BotFather))

### Setup

```bash
git clone https://github.com/Gzeu/ai-sharpness-monitor.git
cd ai-sharpness-monitor

pip install -r requirements.txt

cp .env.example .env
# Edit .env: add CEREBRAS_API_KEY and optionally TELEGRAM_BOT_TOKEN

python run.py
```

That's it. The system:
1. Initializes SQLite DB at `./data/sharpness.db`
2. Runs an immediate probe cycle
3. Starts the scheduler (every 15 min)
4. Starts the API at `http://localhost:8000`
5. Starts the Telegram bot (if token is set)

### Docker (optional)

```bash
docker-compose up -d
```

---

## API Endpoints

```
GET  /scores                       All model scores + market context
GET  /scores/{model}               Single model breakdown
GET  /scores/recommend?task=coding Best model for a task
GET  /scores/history/{model}?hours=24  Score trend (24h)
POST /session/start                Start session tracking
POST /session/{id}/update          Log token usage
POST /session/{id}/feedback        Rate session (1-5)
GET  /health                       Health check
```

### Example: `/scores`

```json
{
  "scores": {
    "llama-3.3-70b": {
      "score": 81,
      "status": "excellent",
      "emoji": "🟢",
      "recommendation": "Use now — peak conditions",
      "latency_ms": 312.4,
      "market": {
        "btc_price": 104250.00,
        "btc_change_1h_pct": 0.42,
        "volatility_level": "calm",
        "ai_load_risk": "low"
      }
    }
  },
  "market": {
    "btc_price": 104250.00,
    "btc_change_1h_pct": 0.42,
    "ai_load_risk": "low",
    "ai_load_message": "BTC calm — AI load risk low"
  }
}
```

---

## Telegram Bot Commands

```
/status          All model scores + BTC market context
/best [task]     Best model right now (optionally for a task)
/market          BTC price, volatility, AI load risk
/context <pct>   Check context window health (e.g. /context 65)
/history [model] 24h score trend
/help            All commands
```

**Automatic alerts:** when a model's score drops ≥15 points between probe cycles, the bot sends an alert to your chat automatically.

---

## BTC → AI Load Correlation

The `ai_load_risk` field is computed from:

1. **Realized volatility** (annualized, 60-min window of 1m candles)
2. **Absolute 1h price change** (% move regardless of direction)

| Condition | Risk Level | Score Impact |
|---|---|---|
| Vol < 0.5, \|Δ1h\| < 0.5% | low | +10pts |
| Vol 0.5–1.0 or \|Δ1h\| 0.5–1.5% | medium | +7pts |
| Vol 1.0–2.0 or \|Δ1h\| 1.5–3.0% | high | +4pts |
| Vol > 2.0 or \|Δ1h\| > 3.0% | very_high | +1pt |

High/very_high risk also appends a warning string to the model recommendation.

---

## Roadmap

- [x] Cerebras free API prober
- [x] Sharpness scorer (rules-based)
- [x] BTC volatility + AI load risk
- [x] SQLite local persistence
- [x] Telegram bot + automatic alerts
- [x] Session tracking + personal feedback
- [ ] Streamlit dashboard (score trends, BTC correlation chart)
- [ ] Personal ML model (Logistic Regression on session history)
- [ ] ETH volatility as additional proxy
- [ ] Context window auto-warning hook (intercept API responses)
- [ ] Export history to CSV

---

## Cost

**$0/month.** Everything runs locally. The only network calls are:
- Cerebras free API (probe every 15min, ~5 tokens/probe)
- Binance public REST API (no authentication)
- Telegram Bot API (push only)

---

## License

MIT © 2026 George Pricop
