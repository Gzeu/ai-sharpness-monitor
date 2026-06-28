"""Streamlit dashboard — real-time AI Sharpness Monitor visualization.

Run: streamlit run dashboard/app.py
Requires API to be running on localhost:8000
"""
import streamlit as st
import httpx
import pandas as pd
import altair as alt
from datetime import datetime, timezone
import time

API_BASE = "http://localhost:8000"

st.set_page_config(
    page_title="AI Sharpness Monitor",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Minimal custom CSS ────────────────────────────────────────────────────
st.markdown("""
<style>
  .metric-card { background: #1c1b19; border-radius: 12px; padding: 16px 20px; border: 1px solid #2a2926; }
  .score-excellent { color: #4f98a3; font-size: 2.5rem; font-weight: 700; }
  .score-good { color: #6daa45; font-size: 2.5rem; font-weight: 700; }
  .score-degraded { color: #fdab43; font-size: 2.5rem; font-weight: 700; }
  .score-poor { color: #dd6974; font-size: 2.5rem; font-weight: 700; }
  .btc-alert { background: #2d1f00; border: 1px solid #fdab43; border-radius: 8px; padding: 12px 16px; }
  .stMetric label { color: #797876 !important; font-size: 0.8rem !important; }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=30)
def fetch_scores():
    try:
        r = httpx.get(f"{API_BASE}/scores", timeout=5)
        return r.json()
    except Exception:
        return None


@st.cache_data(ttl=60)
def fetch_history(model: str, hours: int = 24):
    try:
        r = httpx.get(f"{API_BASE}/scores/history/{model}", params={"hours": hours}, timeout=5)
        return r.json().get("history", [])
    except Exception:
        return []


def score_class(score: int) -> str:
    if score >= 80: return "excellent"
    if score >= 60: return "good"
    if score >= 40: return "degraded"
    return "poor"


def render_score_badge(score: int) -> str:
    cls = score_class(score)
    emojis = {"excellent": "🟢", "good": "🟡", "degraded": "🟠", "poor": "🔴"}
    return f"{emojis[cls]} {score}/100"


# ── Header ───────────────────────────────────────────────────────────────
col_title, col_time, col_refresh = st.columns([3, 2, 1])
with col_title:
    st.markdown("## 🤖 AI Sharpness Monitor")
with col_time:
    st.caption(f"Last updated: {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}")
with col_refresh:
    if st.button("🔄 Refresh"):
        st.cache_data.clear()
        st.rerun()

st.divider()

# ── Fetch data ───────────────────────────────────────────────────────────
data = fetch_scores()

if not data or not data.get("scores"):
    st.warning("⏳ Waiting for first probe cycle (starts ~30s after API launch)...")
    st.info("Make sure the API is running: `python run.py --api`")
    st.stop()

scores = data["scores"]
market = data.get("market") or {}

# ── Market context banner ────────────────────────────────────────────────────
if market:
    risk = market.get("ai_load_risk", "unknown")
    btc_price = market.get("btc_price", 0)
    change_1h = market.get("btc_change_1h_pct", 0)
    vol_level = market.get("volatility_level", "unknown")

    risk_colors = {"low": "🟢", "medium": "🟡", "high": "🟠", "very_high": "🔴", "unknown": "⚪"}
    risk_icon = risk_colors.get(risk, "⚪")

    market_cols = st.columns(5)
    market_cols[0].metric("₿ BTC Price", f"${btc_price:,.0f}")
    market_cols[1].metric("1h Change", f"{change_1h:+.2f}%")
    market_cols[2].metric("24h Change", f"{market.get('btc_change_24h_pct', 0):+.2f}%")
    market_cols[3].metric("Volatility", vol_level.capitalize())
    market_cols[4].metric("AI Load Risk", f"{risk_icon} {risk.replace('_', ' ').title()}")

    if risk in ("high", "very_high"):
        st.markdown(
            f'<div class="btc-alert">⚡ <strong>BTC Alert:</strong> {market.get("ai_load_message", "")} '
            f'| BTC {change_1h:+.2f}% (1h)</div>',
            unsafe_allow_html=True,
        )
    st.divider()

# ── Model score cards ─────────────────────────────────────────────────────────
st.subheader("Current Sharpness Scores")

sorted_models = sorted(scores.items(), key=lambda x: x[1]["score"], reverse=True)
cols = st.columns(min(len(sorted_models), 4))

for i, (model, mdata) in enumerate(sorted_models):
    with cols[i % 4]:
        score = mdata["score"]
        cls = score_class(score)
        bd = mdata.get("breakdown", {})
        st.markdown(f"**{model}**")
        st.markdown(
            f'<span class="score-{cls}">{mdata["emoji"]} {score}/100</span>',
            unsafe_allow_html=True,
        )
        st.caption(mdata["recommendation"])
        st.caption(f"⚡ {mdata['latency_ms']:.0f}ms")
        with st.expander("Score breakdown"):
            bd_df = pd.DataFrame([
                {"Component": k.replace("_score", "").replace("_", " ").title(), "Score": v, "Max": [25,25,15,15,10,10][j]}
                for j, (k, v) in enumerate(bd.items())
            ])
            chart = alt.Chart(bd_df).mark_bar(cornerRadius=4).encode(
                x=alt.X("Score:Q", scale=alt.Scale(domain=[0, 25])),
                y=alt.Y("Component:N", sort="-x"),
                color=alt.condition(
                    alt.datum.Score >= alt.datum.Max * 0.7,
                    alt.value("#4f98a3"),
                    alt.value("#fdab43"),
                ),
                tooltip=["Component", "Score", "Max"],
            ).properties(height=200)
            st.altair_chart(chart, use_container_width=True)

st.divider()

# ── Score history chart ─────────────────────────────────────────────────────
st.subheader("Score History (24h)")

col_model, col_hours = st.columns([3, 1])
with col_model:
    selected_model = st.selectbox("Model", list(scores.keys()), label_visibility="collapsed")
with col_hours:
    hours = st.selectbox("Window", [6, 12, 24, 48], index=2, label_visibility="collapsed")

history = fetch_history(selected_model, hours)

if history:
    df = pd.DataFrame(history)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["btc_change_abs"] = df["btc_change_1h_pct"].abs()

    # Score line
    score_line = alt.Chart(df).mark_line(strokeWidth=2, color="#4f98a3").encode(
        x=alt.X("timestamp:T", title="Time (UTC)"),
        y=alt.Y("score:Q", scale=alt.Scale(domain=[0, 100]), title="Sharpness Score"),
        tooltip=["timestamp:T", "score:Q", "latency_ms:Q", "ai_load_risk:N"],
    )
    score_points = alt.Chart(df).mark_circle(size=40, color="#4f98a3").encode(
        x="timestamp:T",
        y="score:Q",
    )

    # BTC change bars on secondary axis
    btc_bars = alt.Chart(df).mark_bar(opacity=0.25, color="#fdab43").encode(
        x="timestamp:T",
        y=alt.Y("btc_change_abs:Q", title="|BTC 1h %|", scale=alt.Scale(domain=[0, 10])),
    )

    # Threshold lines
    thresholds = pd.DataFrame([{"y": 80, "label": "Excellent"}, {"y": 60, "label": "Good"}, {"y": 40, "label": "Degraded"}])
    threshold_lines = alt.Chart(thresholds).mark_rule(strokeDash=[4, 4], opacity=0.4).encode(
        y="y:Q",
        color=alt.value("#797876"),
    )

    chart = alt.layer(score_line, score_points, threshold_lines).resolve_scale(
        y="independent"
    ).properties(height=320)

    st.altair_chart(chart, use_container_width=True)

    # Stats row
    sc = df["score"]
    stat_cols = st.columns(5)
    stat_cols[0].metric("Latest", f"{sc.iloc[-1]}/100")
    stat_cols[1].metric("Average", f"{sc.mean():.1f}")
    stat_cols[2].metric("Min", f"{sc.min()}")
    stat_cols[3].metric("Max", f"{sc.max()}")
    trend = sc.iloc[-1] - sc.iloc[0] if len(sc) > 1 else 0
    stat_cols[4].metric("Trend", f"{trend:+.0f} pts")

    # CSV export
    csv = df.to_csv(index=False)
    st.download_button(
        label="↓ Export CSV",
        data=csv,
        file_name=f"sharpness_{selected_model.replace('/', '_')}_{hours}h.csv",
        mime="text/csv",
    )
else:
    st.info("No history yet — scores are saved every probe cycle (15 min). Come back soon.")

# ── BTC correlation scatter ──────────────────────────────────────────────────
if history and len(history) > 5:
    st.divider()
    st.subheader("BTC Volatility ↔ AI Sharpness Correlation")
    st.caption("Each point = one probe cycle. Trend: high BTC movement → lower AI scores.")

    scatter = alt.Chart(df).mark_circle(size=60, opacity=0.7).encode(
        x=alt.X("btc_change_abs:Q", title="|BTC 1h change %|"),
        y=alt.Y("score:Q", title="Sharpness Score", scale=alt.Scale(domain=[0, 100])),
        color=alt.Color("ai_load_risk:N", scale=alt.Scale(
            domain=["low", "medium", "high", "very_high"],
            range=["#4f98a3", "#6daa45", "#fdab43", "#dd6974"],
        )),
        tooltip=["timestamp:T", "score:Q", "btc_change_1h_pct:Q", "ai_load_risk:N", "latency_ms:Q"],
    )
    regression = scatter.transform_regression(
        "btc_change_abs", "score"
    ).mark_line(color="#797876", strokeDash=[4, 4], opacity=0.6)

    st.altair_chart((scatter + regression).properties(height=280), use_container_width=True)

# ── Auto-refresh every 60s ──────────────────────────────────────────────────
st.markdown("---")
st.caption("🔄 Auto-refreshes every 60s. Probe cycle runs every 15 min. [API docs](http://localhost:8000/docs)")
time.sleep(1)  # tiny delay before rerun to avoid tight loop
st.rerun() if st.session_state.get("auto_refresh", True) else None
