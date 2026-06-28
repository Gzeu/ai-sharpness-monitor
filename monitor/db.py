"""SQLite persistence layer — no server needed, file stored in ./data/sharpness.db."""
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, Column, Integer, Float, String, Boolean, DateTime, Text
from sqlalchemy.orm import DeclarativeBase, Session
from monitor.config import settings
import structlog

log = structlog.get_logger()

# ── SQLAlchemy setup ───────────────────────────────────────────────────────────
Path("data").mkdir(exist_ok=True)

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=False,
)


class Base(DeclarativeBase):
    pass


class ProbeLogORM(Base):
    __tablename__ = "probe_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    model = Column(String(100), nullable=False, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    latency_ms = Column(Float)
    ttft_ms = Column(Float, nullable=True)
    success = Column(Boolean)
    error = Column(Text, nullable=True)
    tokens_used = Column(Integer, default=0)


class SharpnessScoreORM(Base):
    __tablename__ = "sharpness_scores"
    id = Column(Integer, primary_key=True, autoincrement=True)
    model = Column(String(100), nullable=False, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    total_score = Column(Integer)
    time_score = Column(Integer)
    latency_score = Column(Integer)
    error_rate_score = Column(Integer)
    context_score = Column(Integer)
    volatility_score = Column(Integer)
    personal_score = Column(Integer)
    latency_ms = Column(Float)
    btc_volatility = Column(Float)
    btc_price = Column(Float)
    btc_change_1h_pct = Column(Float)
    ai_load_risk = Column(String(20))


class SessionLogORM(Base):
    __tablename__ = "session_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(50), unique=True)
    model = Column(String(100))
    started_at = Column(DateTime)
    ended_at = Column(DateTime, nullable=True)
    tokens_used = Column(Integer, default=0)
    peak_context_pct = Column(Float, default=0.0)
    feedback_score = Column(Integer, nullable=True)
    task_type = Column(String(50), nullable=True)


def init_db():
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)
    log.info("db_initialized", path=settings.database_url)


async def save_probe_log(result) -> None:
    """Persist a probe result to SQLite."""
    loop = asyncio.get_event_loop()
    def _write():
        with Session(engine) as session:
            session.add(ProbeLogORM(
                model=result.model,
                timestamp=result.timestamp,
                latency_ms=result.latency_ms,
                ttft_ms=result.ttft_ms,
                success=result.success,
                error=result.error,
                tokens_used=result.tokens_used,
            ))
            session.commit()
    await loop.run_in_executor(None, _write)


async def save_sharpness_score(score, btc_volatility: float = 0.0) -> None:
    """Persist a sharpness score to SQLite."""
    loop = asyncio.get_event_loop()
    def _write():
        with Session(engine) as session:
            session.add(SharpnessScoreORM(
                model=score.model,
                timestamp=score.timestamp,
                total_score=score.total,
                time_score=score.time_score,
                latency_score=score.latency_score,
                error_rate_score=score.error_rate_score,
                context_score=score.context_score,
                volatility_score=score.volatility_score,
                personal_score=score.personal_score,
                latency_ms=score.latency_ms,
                btc_volatility=btc_volatility,
                btc_price=score.btc_price,
                btc_change_1h_pct=score.btc_change_1h_pct,
                ai_load_risk=score.ai_load_risk,
            ))
            session.commit()
    await loop.run_in_executor(None, _write)


def get_personal_success_rate(model: str, limit: int = 50) -> float:
    """Compute personal success rate from session feedback. -1 if no data."""
    with Session(engine) as session:
        rows = (
            session.query(SessionLogORM.feedback_score)
            .filter(
                SessionLogORM.model == model,
                SessionLogORM.feedback_score.isnot(None),
            )
            .order_by(SessionLogORM.id.desc())
            .limit(limit)
            .all()
        )
    if not rows:
        return -1.0
    scores = [r[0] for r in rows]
    # Normalize: 1-5 rating → 0.0-1.0, consider 4+ as success
    successes = sum(1 for s in scores if s >= 4)
    return successes / len(scores)


def get_score_history(model: str, hours: int = 24) -> list:
    """Fetch score history for trend display."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    with Session(engine) as session:
        rows = (
            session.query(SharpnessScoreORM)
            .filter(SharpnessScoreORM.model == model, SharpnessScoreORM.timestamp >= cutoff)
            .order_by(SharpnessScoreORM.timestamp.asc())
            .all()
        )
    return [
        {
            "timestamp": r.timestamp.isoformat(),
            "score": r.total_score,
            "btc_price": r.btc_price,
            "btc_change_1h_pct": r.btc_change_1h_pct,
            "ai_load_risk": r.ai_load_risk,
            "latency_ms": r.latency_ms,
        }
        for r in rows
    ]
