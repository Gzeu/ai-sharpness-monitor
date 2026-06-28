"""Score endpoints — includes market context in every response."""
from fastapi import APIRouter, HTTPException
from monitor.scheduler import get_latest_scores, get_last_market
from monitor.db import get_score_history
from monitor.market import BTC_IMPACT_MESSAGES

router = APIRouter()


@router.get("")
async def get_all_scores():
    """Return sharpness scores for all monitored models + current market context."""
    scores = get_latest_scores()
    market = get_last_market()

    market_ctx = None
    if market:
        market_ctx = {
            "btc_price": market.btc_price,
            "btc_change_1h_pct": market.price_change_1h_pct,
            "btc_change_24h_pct": market.price_change_24h_pct,
            "volatility_level": market.volatility_level,
            "ai_load_risk": market.ai_load_risk,
            "ai_load_message": BTC_IMPACT_MESSAGES.get(market.ai_load_risk, ""),
        }

    if not scores:
        return {
            "message": "Probe cycle starting — check back in ~30 seconds.",
            "scores": {},
            "market": market_ctx,
        }
    return {"scores": scores, "count": len(scores), "market": market_ctx}


@router.get("/recommend")
async def recommend_model(task: str = "general"):
    """Return the best model for a given task type."""
    scores = get_latest_scores()
    if not scores:
        raise HTTPException(status_code=503, detail="No score data yet.")

    best_model, best_data = max(scores.items(), key=lambda x: x[1]["score"])
    market = get_last_market()

    return {
        "task": task,
        "recommended_model": best_model,
        "score": best_data["score"],
        "status": best_data["status"],
        "recommendation": best_data["recommendation"],
        "market_warning": BTC_IMPACT_MESSAGES.get(market.ai_load_risk, "") if market else None,
    }


@router.get("/history/{model_id:path}")
async def get_model_history(model_id: str, hours: int = 24):
    """Return score history for trend analysis."""
    history = get_score_history(model_id, hours=hours)
    if not history:
        raise HTTPException(status_code=404, detail="No history found for this model.")
    return {"model": model_id, "hours": hours, "data_points": len(history), "history": history}


@router.get("/{model_id:path}")
async def get_model_score(model_id: str):
    """Return detailed score breakdown for a specific model."""
    scores = get_latest_scores()
    if model_id not in scores:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found or not yet probed.")
    return {"model": model_id, **scores[model_id]}
