"""SQLite persistence via SQLAlchemy — probe logs, scores, sessions."""
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import structlog
from sqlalchemy import (
    create_engine, Column, String, Float, Integer,
    Boolean, DateTime, Text, Index, func,
)
from sqlalchemy.orm import declarative_base, Session

log = structlog.get_logger()
DB_PATH = Path("data/sharpness.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
Base = declarative_base()


class ProbeLog(Base):
    __tablename__ = "probe_logs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    model = Column(String(100), index=True)
    latency_ms = Column(Float)
    error = Column(Text, nullable=True)
    score = Column(Integer)
    btc_change_1h = Column(Float, default=0.0)
    eth_change_1h = Column(Float, default=0.0)
    ai_load_risk = Column(String(20), default="unknown")


class SessionLog(Base):
    __tablename__ = "sessions"
    id = Column(String(64), primary_key=True)
    model = Column(String(100), index=True)
    started_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime, nullable=True)
    tokens_used = Column(Integer, default=0)
    max_context = Column(Integer, default=200000)
    feedback_rating = Column(Integer, nullable=True)  # 1-5
    active = Column(Boolean, default=True)


Index("ix_probe_model_ts", ProbeLog.model, ProbeLog.timestamp)


def init_db():
    Base.metadata.create_all(engine)
    log.info("db_initialized", path=str(DB_PATH))


def save_probe_log(
    model: str,
    latency_ms: float,
    error: Optional[str],
    score: int,
    btc_change_1h: float = 0.0,
    eth_change_1h: float = 0.0,
    ai_load_risk: str = "unknown",
):
    with Session(engine) as s:
        s.add(ProbeLog(
            model=model,
            latency_ms=latency_ms,
            error=error,
            score=score,
            btc_change_1h=btc_change_1h,
            eth_change_1h=eth_change_1h,
            ai_load_risk=ai_load_risk,
        ))
        s.commit()


def save_score(model: str, score: int):
    """Alias kept for backward compat."""
    pass


def get_score_history(model: str, hours: int = 24) -> list[dict]:
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    with Session(engine) as s:
        rows = (
            s.query(ProbeLog)
            .filter(ProbeLog.model == model, ProbeLog.timestamp >= since)
            .order_by(ProbeLog.timestamp.asc())
            .all()
        )
    return [
        {
            "timestamp": r.timestamp.isoformat() if r.timestamp else None,
            "model": r.model,
            "score": r.score,
            "latency_ms": r.latency_ms,
            "btc_change_1h_pct": r.btc_change_1h,
            "eth_change_1h_pct": r.eth_change_1h,
            "ai_load_risk": r.ai_load_risk,
            "error": r.error,
        }
        for r in rows
    ]


def get_session(session_id: str) -> Optional[SessionLog]:
    with Session(engine) as s:
        return s.get(SessionLog, session_id)


def upsert_session(session_id: str, **kwargs) -> SessionLog:
    with Session(engine) as s:
        obj = s.get(SessionLog, session_id)
        if obj is None:
            obj = SessionLog(id=session_id, **kwargs)
            s.add(obj)
        else:
            for k, v in kwargs.items():
                setattr(obj, k, v)
        s.commit()
        s.refresh(obj)
        return obj
