# AI Sharpness Monitor

> Predict and alert in real-time when an LLM is at peak performance — before wasting a long session on degraded output.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green.svg)](https://fastapi.tiangolo.com)
[![Streamlit](https://img.shields.io/badge/Dashboard-Streamlit-red.svg)](https://streamlit.io)
[![Cost](https://img.shields.io/badge/Cost-$0%2Fmonth-brightgreen.svg)](#cost)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Why this exists

LLM quality is **not constant**. The same model gives dramatically different responses depending on:

- **Server load** — peak US/EU business hours degrade responses
- **Context window saturation** — >60% used → model forgets earlier context (U-shaped loss)
- **BTC + ETH volatility** — when crypto moves sharply, a wave of users ask AI about markets → load spike on all providers

This system monitors all three signals and computes a **Sharpness Score (0–100)** per model in real-time.

---

## Stack — 100% Free, 100% Local

| Component | Solution | Cost |
|---|---|---|
| LLM probe API | [Cerebras free tier](https://cloud.cerebras.ai) — llama-3.3-70b | **$0** |
| Database | SQLite local file `./data/sharpness.db` | **$0** |
| Cache | In-memory Python dict | **$0** |
| Market data | Binance public REST (BTC + ETH, no key) | **$0** |
| Hosting | Local — `python run.py` | **$0** |
| Dashboard | Streamlit | **$0** |
| **Total** | | **$0/month** |

---

## Quick Start

```bash
git clone https://github.com/Gzeu/ai-sharpness-monitor.git
cd ai-sharpness-monitor

make install

cp .env.example .env
# Edit .env: CEREBRAS_API_KEY=csk-...  (free at cloud.cerebras.ai)
#            TELEGRAM_BOT_TOKEN=...    (optional, via @BotFather)

make run          # starts API + bot
```

In a second terminal:
```bash
make run-dashboard   # Streamlit at http://localhost:8501
```

---

## Sharpness Score Formula

| Signal | Weight | Notes |
|---|---|---|
| Time of Day / Week | 25pts | Off-peak, weekends score higher |
| API Latency vs baseline | 25pts | EMA baseline, Cerebras is fast |
| Error Rate (60min window) | 15pts | Recent probe failures |
| Context Window Health | 15pts | % of context used in session |
| BTC + ETH Volatility | 10pts | Combined worst-of signal |
| Personal Success Rate | 10pts | Your session feedback history |

### Thresholds

| Score | Status | Action |
|---|---|---|
| 80–100 | 🟢 Excellent | Use now — peak conditions |
| 60–79 | 🟡 Good | OK, monitor context |
| 40–59 | 🟠 Degraded | Expect shorter/generic answers |
| 0–39 | 🔴 Poor | Wait 1-2h or switch model |

---

## Dashboard

Run `make run-dashboard` → `http://localhost:8501`

Features:
- Real-time score cards with breakdown bar charts (per component)
- BTC + ETH market context strip (price, 1h change, volatility, AI load risk)
- 24h score history line chart with BTC volatility overlay
- BTC ↔ AI sharpness correlation scatter plot with regression line
- CSV export button per model
- Auto-refreshes every 60 seconds

---

## Telegram Bot Commands

```
/status          All model scores + market context
/best [task]     Best model right now
/market          BTC + ETH price, volatility, AI load risk
/context <pct>   Context window health (e.g. /context 65)
/history [model] 24h score trend
/export [model]  Download 48h CSV directly in Telegram
/help            All commands
```

**Automatic alerts:** score drops ≥15 pts between probe cycles → bot alerts you instantly.

---

## BTC + ETH → AI Load Logic

Both BTC/USDT and ETH/USDT 1m candles are fetched from Binance public API. The system takes the **worst-of** signal:

| Condition | Risk | Score |
|---|---|---|
| Both calm, \|moves\| < 0.5% | low | +10pts |
| Moderate vol or \|move\| 0.5–1.5% | medium | +7pts |
| Elevated vol or \|move\| 1.5–3.0% | high | +4pts (\-1 extra) |
| Extreme vol or \|move\| > 3.0% | very\_high | +1pt (\-3 extra) |

High/very_high also appends a warning to every model recommendation string.

---

## API Endpoints

```
GET  /scores                        All scores + market context
GET  /scores/{model}                Single model breakdown
GET  /scores/recommend?task=coding  Best model for task
GET  /scores/history/{model}?hours=24  Score history
GET  /scores/export/{model}?hours=24   Download CSV
POST /session/start                 Start session tracking
POST /session/{id}/update           Log token usage
POST /session/{id}/feedback         Rate session (1-5)
GET  /health                        Health check
```

---

## Project Structure

```
ai-sharpness-monitor/
├── monitor/          Core logic (prober, scorer, market, context, DB)
├── api/              FastAPI REST endpoints
├── bot/              Telegram bot
├── dashboard/        Streamlit visual dashboard
├── tests/            pytest suite
├── data/             SQLite DB (gitignored, auto-created)
├── run.py            Unified launcher
├── Makefile          Developer shortcuts
└── .env.example      Config template
```

---

## Roadmap

- [x] Cerebras free API prober
- [x] Sharpness scorer (rules-based)
- [x] BTC + ETH volatility dual proxy
- [x] SQLite local persistence
- [x] Telegram bot + automatic alerts + CSV export
- [x] Session tracking + personal feedback
- [x] Streamlit dashboard (score trends, BTC correlation chart)
- [ ] Personal ML model (Logistic Regression on session history)
- [ ] Context window auto-warning hook (intercept API response headers)
- [ ] OpenTelemetry traces export
- [ ] Multi-user support (per Telegram user_id feedback isolation)

---

## License

MIT © 2026 George Pricop
