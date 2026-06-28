"""SQLAlchemy database models."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, Float, String, Boolean, DateTime, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class ProbeLog(Base):
    """Raw probe results from each latency check."""
    __tablename__ = "probe_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model = Column(String(100), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    latency_ms = Column(Float, nullable=False)
    ttft_ms = Column(Float, nullable=True)
    success = Column(Boolean, nullable=False)
    error = Column(Text, nullable=True)
    tokens_used = Column(Integer, default=0)


class SharpnessScore(Base):
    """Computed sharpness score snapshots."""
    __tablename__ = "sharpness_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model = Column(String(100), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    total_score = Column(Integer, nullable=False)
    time_score = Column(Integer)
    latency_score = Column(Integer)
    error_rate_score = Column(Integer)
    context_score = Column(Integer)
    volatility_score = Column(Integer)
    personal_score = Column(Integer)
    latency_ms = Column(Float)
    btc_volatility = Column(Float)


class SessionLog(Base):
    """User session tracking for personal success rate."""
    __tablename__ = "session_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(50), unique=True, nullable=False)
    model = Column(String(100), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    tokens_used = Column(Integer, default=0)
    peak_context_pct = Column(Float, default=0.0)
    feedback_score = Column(Integer, nullable=True)  # 1-5 rating
    task_type = Column(String(50), nullable=True)  # coding, writing, analysis, etc.
