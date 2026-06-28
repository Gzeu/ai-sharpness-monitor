"""Session tracking endpoints — context window health + personal feedback."""
import uuid
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession
from monitor.db import engine, SessionLogORM
from monitor.context_tracker import should_warn_context, SessionContext
from datetime import datetime, timezone

router = APIRouter()

# In-memory active sessions
_active_sessions: dict[str, SessionContext] = {}


class SessionStartRequest(BaseModel):
    model: str
    task_type: str = "general"


class SessionUpdateRequest(BaseModel):
    tokens_used: int


class SessionFeedbackRequest(BaseModel):
    rating: int  # 1-5
    task_type: str | None = None


@router.post("/start")
async def start_session(req: SessionStartRequest):
    session_id = str(uuid.uuid4())[:8]
    ctx = SessionContext(model=req.model, session_id=session_id)
    _active_sessions[session_id] = ctx

    with DBSession(engine) as db:
        db.add(SessionLogORM(
            session_id=session_id,
            model=req.model,
            started_at=datetime.now(timezone.utc),
            task_type=req.task_type,
        ))
        db.commit()

    return {"session_id": session_id, "model": req.model, "context_window": ctx.context_window}


@router.post("/{session_id}/update")
async def update_session(session_id: str, req: SessionUpdateRequest):
    ctx = _active_sessions.get(session_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Session not found.")

    ctx.add_tokens(req.tokens_used)
    warn, msg = should_warn_context(ctx)
    return {
        "session_id": session_id,
        "tokens_used": ctx.tokens_used,
        "usage_pct": round(ctx.usage_percent * 100, 1),
        "health": ctx.health_status,
        "warn": warn,
        "message": msg if warn else "Context healthy.",
    }


@router.post("/{session_id}/feedback")
async def session_feedback(session_id: str, req: SessionFeedbackRequest):
    if req.rating < 1 or req.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be 1-5.")

    ctx = _active_sessions.pop(session_id, None)

    with DBSession(engine) as db:
        row = db.query(SessionLogORM).filter(SessionLogORM.session_id == session_id).first()
        if row:
            row.ended_at = datetime.now(timezone.utc)
            row.feedback_score = req.rating
            if ctx:
                row.tokens_used = ctx.tokens_used
                row.peak_context_pct = ctx.usage_percent
            if req.task_type:
                row.task_type = req.task_type
            db.commit()

    return {"session_id": session_id, "rating": req.rating, "saved": True}
