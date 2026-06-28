"""Score endpoints."""
from fastapi import APIRouter, HTTPException
from monitor.scheduler import get_latest_scores

router = APIRouter()


@router.get("")
async def get_all_scores():
    """Return sharpness scores for all monitored models."""
    scores = get_latest_scores()
    if not scores:
        return {"message": "No data yet — probe cycle hasn't run. Try again in 30 seconds.", "scores": {}}
    return {"scores": scores, "count": len(scores)}


@router.get("/recommend")
async def recommend_model(task: str = "general"):
    """Return the best model for a given task type."""
    scores = get_latest_scores()
    if not scores:
        raise HTTPException(status_code=503, detail="No score data available yet.")

    # Simple recommendation: highest score wins
    # Future: weight by task type (coding vs creative vs analysis)
    best_model = max(scores.items(), key=lambda x: x[1]["score"])
    return {
        "task": task,
        "recommended_model": best_model[0],
        "score": best_model[1]["score"],
        "status": best_model[1]["status"],
        "recommendation": best_model[1]["recommendation"],
    }


@router.get("/{model_id:path}")
async def get_model_score(model_id: str):
    """Return detailed score breakdown for a specific model."""
    scores = get_latest_scores()
    if model_id not in scores:
        raise HTTPException(status_code=404, detail=f"Model '{model_id}' not found or not yet probed.")
    return {"model": model_id, **scores[model_id]}
