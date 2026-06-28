"""Feedback endpoints — rate sessions, view ML training data readiness."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from monitor.feedback import save_feedback, load_feedback, personal_success_rate, training_data_summary
from monitor.scheduler import get_latest_scores, get_last_market

router = APIRouter()


class FeedbackIn(BaseModel):
    session_id: str
    model: str
    rating: int = Field(..., ge=1, le=5, description="1=terrible, 5=excellent")
    tokens_used: Optional[int] = None
    notes: Optional[str] = None


@router.post("")
async def submit_feedback(body: FeedbackIn):
    scores = get_latest_scores()
    market = get_last_market()

    model_data = scores.get(body.model, {})
    breakdown = model_data.get("breakdown", {})
    sharpness = model_data.get("score", 50)

    btc_change = market.btc_change_1h_pct if market else 0.0
    eth_change = market.eth_change_1h_pct if market else 0.0

    record = save_feedback(
        session_id=body.session_id,
        model=body.model,
        rating=body.rating,
        sharpness_score_at_start=sharpness,
        breakdown_at_start=breakdown,
        btc_change_at_start=btc_change,
        eth_change_at_start=eth_change,
        tokens_used=body.tokens_used,
        notes=body.notes,
    )
    return {"saved": True, "label": record["label"], "model": body.model, "rating": body.rating}


@router.get("/summary")
async def feedback_summary():
    return training_data_summary()


@router.get("/success-rate/{model_id:path}")
async def model_success_rate(model_id: str):
    rate = personal_success_rate(model_id)
    return {"model": model_id, "personal_success_rate": rate, "as_pct": f"{rate*100:.1f}%"}


@router.get("/history")
async def feedback_history(model: Optional[str] = None, limit: int = 50):
    records = load_feedback(model)
    return {"count": len(records), "records": records[-limit:]}
