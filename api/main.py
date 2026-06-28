"""FastAPI application entry point — v0.3.0"""
import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from monitor.db import init_db
from monitor.scheduler import create_scheduler, run_probe_cycle
from monitor.alerts import get_alert_manager
from api.routes import scores, health, sessions, feedback

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup", version="0.3.0")
    init_db()
    asyncio.create_task(run_probe_cycle())  # immediate first probe
    scheduler = create_scheduler()
    scheduler.start()
    log.info("scheduler_started", interval_minutes=15)
    yield
    scheduler.shutdown()
    log.info("shutdown")


app = FastAPI(
    title="AI Sharpness Monitor",
    description=(
        "Real-time LLM performance scoring.\n\n"
        "Signals: Cerebras API latency + BTC/ETH volatility proxy + time patterns + context health.\n"
        "Cost: $0/month (SQLite local + Binance public API).\n\n"
        "Dashboard: open `dashboard/index.html` in browser while API is running."
    ),
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(scores.router,   prefix="/scores",   tags=["scores"])
app.include_router(sessions.router, prefix="/session",  tags=["sessions"])
app.include_router(feedback.router, prefix="/feedback", tags=["feedback"])
app.include_router(health.router,   prefix="/health",   tags=["health"])

# Serve dashboard as static site at /dashboard
dashboard_dir = Path(__file__).parent.parent / "dashboard"
if dashboard_dir.exists():
    app.mount("/dashboard", StaticFiles(directory=str(dashboard_dir), html=True), name="dashboard")
    log.info("dashboard_mounted", url="http://localhost:8000/dashboard")
