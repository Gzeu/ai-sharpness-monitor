"""FastAPI application entry point."""
import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from monitor.db import init_db
from monitor.scheduler import create_scheduler, run_probe_cycle
from api.routes import scores, health, sessions

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup")
    init_db()  # creates SQLite tables if not exist
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
        "Real-time LLM performance scoring — Cerebras free API + BTC volatility proxy.\n\n"
        "Stack: Python + FastAPI + SQLite (local) + CCXT Binance public API.\n"
        "Cost: $0/month."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scores.router, prefix="/scores", tags=["scores"])
app.include_router(sessions.router, prefix="/session", tags=["sessions"])
app.include_router(health.router, prefix="/health", tags=["health"])
