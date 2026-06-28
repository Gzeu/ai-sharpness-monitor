# AI Sharpness Monitor

> Predict and alert in real-time when an LLM is at peak performance — before wasting a long session on degraded output.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green.svg)](https://fastapi.tiangolo.com)
[![Dashboard](https://img.shields.io/badge/Dashboard-HTML%2FJS-4f98a3.svg)](#dashboard)
[![Cost](https://img.shields.io/badge/Cost-$0%2Fmonth-brightgreen.svg)](#stack)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Why this exists

LLM quality is **not constant**. The same model gives dramatically different responses depending on:

- **Server load** — peak US/EU business hours (13–22 UTC) degrade response quality
- **Context window saturation** — >60% used → U-shaped loss, model forgets earlier context
- **BTC + ETH volatility** — sharp crypto moves trigger a wave of AI queries → load spike on all providers
- **Personal history** — your own session outcomes per model, stored locally

This system monitors all four signals continuously and computes a **Sharpness Score (0–100)** per model in real-time, with Telegram alerts and a zero-dependency HTML dashboard.

---

## Stack — 100% Free, 100% Local

| Component | Solution | Cost |
|---|---|---|
| LLM probe API | [Cerebras free tier](https://cloud.cerebras.ai) — `llama-3.3-70b`, `llama-3.1-8b` | **$0** |
| Database | SQLite — `./data/sharpness.db` (auto-created) | **$0** |
| Market data | Binance public REST — BTC + ETH OHLCV, no API key | **$0** |
| Dashboard | Pure HTML/JS — served by FastAPI at `/dashboard` | **$0** |
| Telegram bot | Optional — `python-telegram-bot` | **$0** |
| Hosting | Local — `python run.py` | **$0** |
| **Total** | | **$0/month** |

---

## Quick Start

```bash
git clone https://github.com/Gzeu/ai-sharpness-monitor.git
cd ai-sharpness-monitor

make install

cp .env.example .env
# Required: CEREBRAS_API_KEY=csk-...   (free at cloud.cerebras.ai — no credit card)
# Optional: TELEGRAM_BOT_TOKEN=...     (via @BotFather)

make run          # API on http://localhost:8000
make dashboard    # opens http://localhost:8000/dashboard in browser
```

API docs auto-generated at `http://localhost:8000/docs`.

---

## Sharpness Score Formula

| Signal | Weight | Notes |
|---|---|---|
| Time of Day / Week | 25 pts | Off-peak hours, weekends score higher |
| API Latency vs EMA baseline | 25 pts | Exponential moving average, α=0.1 |
| Error Rate (60 min rolling) | 15 pts | Recent probe failures penalized hard |
| Context Window Health | 15 pts | % of context window used in active session |
| BTC + ETH Volatility (worst-of) | 10 pts | Combined signal from both assets |
| Personal Success Rate | 10 pts | Your own session feedback history |

### Score Thresholds

| Score | Status | Recommendation |
|---|---|---|
| 80–100 | 🟢 Excellent | Use now — peak conditions |
| 60–79 | 🟡 Good | OK, monitor context window |
| 40–59 | 🟠 Degraded | Expect shorter / generic answers |
| 0–39 | 🔴 Poor | Wait 1–2h or switch model |

---

## Dashboard

Run `make run` then `make dashboard` → opens **`http://localhost:8000/dashboard`**

No extra dependencies. No Streamlit. Served directly by the FastAPI backend.

**Features:**
- Live score cards per model — score badge, latency, breakdown bar chart (6 components)
- BTC + ETH market strip — price, 1h% change, volatility level, AI load risk color-coded
- Alert banner when AI load risk is `high` / `very_high`
- 24h score history chart — score line + latency bars + threshold lines (80 / 60 / 40)
- BTC/ETH ↔ Sharpness correlation scatter plot with color-coded risk dots
- CSV export per model (button in history chart)
- Auto-refresh every 60 seconds, toast notifications for errors

---

## Alert System (with Hysteresis)

Alerts fire via Telegram with **spam protection**:

| Condition | Behavior |
|---|---|
| Score drops ≥ 12 pts | Alert fires — once per 30 min cooldown |
| Score < 35 (critical) | Always fires, ignores cooldown |
| Score recovers ≥ 15 pts after an alert | Positive "recovery" alert |
| Score oscillates ±5 pts | No alert — hysteresis prevents spam |

Recovery tracking: re-alerts are blocked until score climbs ≥ 8 pts above the last alert score.

---

## Telegram Bot Commands

```
/status          All model scores + BTC/ETH market context
/best [task]     Best model right now for a given task
/market          BTC + ETH price, 1h change, volatility, AI load risk
/context <pct>   Context window health (e.g. /context 65)
/history [model] 24h score trend summary
/export [model]  Download 48h CSV directly in Telegram
/help            All commands
```

---

## BTC + ETH → AI Load Signal

Both BTC/USDT and ETH/USDT 1m candles are fetched from Binance public REST (no API key needed). The system takes the **worst-of** signal across both assets:

| Condition | Risk Level | Volatility Score |
|---|---|---|
| Both calm, \|1h move\| < 0.5% | `low` | 10 pts |
| Moderate vol or \|move\| 0.5–1.5% | `medium` | 7 pts |
| Elevated vol or \|move\| 1.5–3.0% | `high` | 4 pts (−1 extra) |
| Extreme vol or \|move\| > 3.0% | `very_high` | 1 pt (−3 extra) |

High/very_high risk appends a warning to every score recommendation and triggers the dashboard alert banner.

---

## Personal Feedback & ML Prep

Every session can be rated 1–5. Feedback is stored in `data/feedback.jsonl` as structured feature vectors:

```bash
# Rate a session via API
curl -X POST http://localhost:8000/feedback \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc123", "model": "llama-3.3-70b", "rating": 5}'

# Check ML training data readiness
curl http://localhost:8000/feedback/summary
# → {"labeled": 12, "ready_for_ml": false, "note": "...when ready_for_ml=True"}
```

When `ready_for_ml: true` (≥ 30 labeled sessions), uncomment `scikit-learn` in `requirements.txt` and run:

```python
from monitor.feedback import get_training_data
X, y = get_training_data()
# → sklearn LogisticRegression().fit(X, y)
```

---

## API Reference

```
GET  /scores                           All scores + market context
GET  /scores/{model}                   Single model score + breakdown
GET  /scores/recommend?task=coding     Best model for task
GET  /scores/history/{model}?hours=24  Score history (saved each probe cycle)
GET  /scores/export/{model}?hours=24   Download CSV
POST /feedback                         Submit session rating (1–5)
GET  /feedback/summary                 ML training data readiness
GET  /feedback/success-rate/{model}    Personal success rate for model
POST /session/start                    Start context tracking session
POST /session/{id}/update              Update token count
GET  /health                           Health check
```

Full interactive docs: `http://localhost:8000/docs`

---

## Project Structure

```
ai-sharpness-monitor/
├── monitor/
│   ├── prober.py          Cerebras API latency probe
│   ├── scorer.py          Sharpness Score formula (rules-based)
│   ├── market.py          BTC + ETH volatility (Binance public)
│   ├── time_patterns.py   Time-of-day / day-of-week scoring
│   ├── context_tracker.py Context window % tracking
│   ├── alerts.py          AlertManager with hysteresis + cooldown
│   ├── feedback.py        Session feedback store + ML feature extraction
│   ├── scheduler.py       APScheduler — probe every 15 min
│   ├── db.py              SQLite via SQLAlchemy
│   └── config.py          Pydantic settings from .env
├── api/
│   ├── main.py            FastAPI app + static dashboard mount
│   └── routes/
│       ├── scores.py      Score endpoints + CSV export
│       ├── sessions.py    Session tracking endpoints
│       ├── feedback.py    Feedback + ML readiness endpoints
│       └── health.py      Health check
├── bot/
│   └── telegram_bot.py    7 commands + automatic alerts
├── dashboard/
│   └── index.html         Pure HTML/JS dashboard (no build step)
├── tests/                 pytest suite
├── data/                  SQLite DB + feedback JSONL (gitignored)
├── run.py                 Unified launcher (--api / --bot / both)
├── Makefile               Developer shortcuts
└── .env.example           Full config reference
```

---

## Makefile Commands

```bash
make install       # pip install -r requirements.txt
make run           # API + bot (if TELEGRAM_BOT_TOKEN set)
make run-api       # API only
make run-bot       # Telegram bot only
make dashboard     # Open http://localhost:8000/dashboard in browser
make test          # pytest -v
make lint          # ruff check
make format        # ruff format
make clean         # remove __pycache__, .pytest_cache
make clean-db      # delete data/ (with confirmation prompt)
```

---

## Roadmap

- [x] Cerebras free API prober (zero cost)
- [x] Sharpness scorer — rules-based, 6 signals
- [x] BTC + ETH dual volatility proxy (worst-of logic)
- [x] SQLite local persistence — probe logs + sessions
- [x] Telegram bot — 7 commands + automatic alerts
- [x] Alert hysteresis — cooldown, recovery tracking, critical override
- [x] Session tracking + personal feedback (JSONL)
- [x] ML feature extraction — `get_training_data()` ready for sklearn
- [x] HTML/JS dashboard — zero deps, served by FastAPI
- [x] CSV export — API endpoint + Telegram command
- [ ] Personal ML model — Logistic Regression on session feedback (needs ≥30 sessions)
- [ ] Context window auto-warning hook (intercept API response headers)
- [ ] OpenTelemetry traces export
- [ ] Multi-user support (per Telegram `user_id` feedback isolation)

---

## License

MIT © 2026 George Pricop
