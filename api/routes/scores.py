"""Score endpoints — includes full market context (BTC + ETH) in every response."""
from fastapi import APIRouter, HTTPException
from monitor.scheduler import get_latest_scores, get_last_market
from monitor.db import get_score_history
from monitor.market import BTC_IMPACT_MESSAGES
import csv
import io
from fastapi.responses import StreamingResponse

router = APIRouter()


def _market_context(market) -> dict | None:
    if not market:
        return None
    return {
        "btc_price": market.btc_price,
        "btc_change_1h_pct": market.btc_change_1h_pct,
        "btc_change_24h_pct": market.btc_change_24h_pct,
        "btc_volatility_level": market.btc_volatility_level,
        "eth_price": market.eth_price,
        "eth_change_1h_pct": market.eth_change_1h_pct,
        "eth_volatility_level": market.eth_volatility_level,
        "combined_volatility_level": market.volatility_level,
        "ai_load_risk": market.ai_load_risk,
        "ai_load_message": BTC_IMPACT_MESSAGES.get(market.ai_load_risk, ""),
    }


@router.get("")
async def get_all_scores():
    scores = get_latest_scores()
    market = get_last_market()
    if not scores:
        return {"message": "Probe cycle starting — check back in ~30s.", "scores": {}, "market": _market_context(market)}
    return {"scores": scores, "count": len(scores), "market": _market_context(market)}


@router.get("/recommend")
async def recommend_model(task: str = "general"):
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


@router.get("/export/{model_id:path}")
async def export_model_csv(model_id: str, hours: int = 24):
    """Export score history as CSV download."""
    history = get_score_history(model_id, hours=hours)
    if not history:
        raise HTTPException(status_code=404, detail="No history found.")

    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=history[0].keys())
    writer.writeheader()
    writer.writerows(history)

    filename = f"sharpness_{model_id.replace('/', '_')}_{hours}h.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/history/{model_id:path}")
async def get_model_history(model_id: str, hours: int = 24):
    history = get_score_history(model_id, hours=hours)
    if not history:
        raise HTTPException(status_code=404, detail="No history found for this model.")
    return {"model": model_id, "hours": hours, "data_points": len(history), "history": history}


@router.get("/{model_id:path}")
async def get_model_score(model_id: str):
    scores = get_latest_scores()
    if model_id not in scores:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found.")
    return {"model": model_id, **scores[model_id]}
