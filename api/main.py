"""FastAPI application entry point."""
import asyncio
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from monitor.scheduler import create_scheduler, run_probe_cycle
from api.routes import scores, health

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("startup")
    # Run one probe immediately on startup
    asyncio.create_task(run_probe_cycle())
    scheduler = create_scheduler()
    scheduler.start()
    log.info("scheduler_started", interval_minutes=10)
    yield
    scheduler.shutdown()
    log.info("shutdown")


app = FastAPI(
    title="AI Sharpness Monitor",
    description="Real-time LLM performance scoring based on latency, load, and context health.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scores.router, prefix="/scores", tags=["scores"])
app.include_router(health.router, prefix="/health", tags=["health"])
