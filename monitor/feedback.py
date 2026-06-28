"""Personal feedback store — prepares data for future ML model.

Stores session-level outcomes tied to the conditions at session start.
Outputs a feature vector per session ready for Logistic Regression training:

  Features (X):
    time_score, latency_score, error_score, context_score,
    volatility_score, btc_change_abs, eth_change_abs,
    hour_utc, day_of_week, model_encoded

  Label (y):
    1 = session_rating >= 4 (good), 0 = session_rating <= 2 (bad)
    Sessions with rating 3 are excluded (neutral — noisy for training)
"""
import json
import os
import structlog
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

log = structlog.get_logger()
FEEDBACK_FILE = Path("data/feedback.jsonl")


def save_feedback(
    session_id: str,
    model: str,
    rating: int,                # 1-5
    sharpness_score_at_start: int,
    breakdown_at_start: dict,
    btc_change_at_start: float,
    eth_change_at_start: float,
    tokens_used: Optional[int] = None,
    notes: Optional[str] = None,
) -> dict:
    """Persist a feedback record and return the feature dict."""
    FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now(timezone.utc)
    record = {
        "session_id": session_id,
        "model": model,
        "rating": rating,
        "label": 1 if rating >= 4 else (0 if rating <= 2 else None),  # None = excluded
        "sharpness_score": sharpness_score_at_start,
        "breakdown": breakdown_at_start,
        "btc_change_abs": abs(btc_change_at_start),
        "eth_change_abs": abs(eth_change_at_start),
        "hour_utc": now.hour,
        "day_of_week": now.weekday(),  # 0=Mon, 6=Sun
        "tokens_used": tokens_used,
        "notes": notes,
        "timestamp": now.isoformat(),
    }

    with open(FEEDBACK_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")

    log.info("feedback_saved", session_id=session_id, model=model, rating=rating, label=record["label"])
    return record


def load_feedback(model: Optional[str] = None) -> list[dict]:
    """Load all feedback, optionally filtered by model."""
    if not FEEDBACK_FILE.exists():
        return []
    records = []
    with open(FEEDBACK_FILE) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
                if model is None or r["model"] == model:
                    records.append(r)
            except json.JSONDecodeError:
                continue
    return records


def personal_success_rate(model: str, recent_n: int = 20) -> float:
    """
    Returns success rate (0.0-1.0) from the last N labeled sessions for this model.
    Used as the 'personal' component in the Sharpness Score.
    """
    records = load_feedback(model)
    labeled = [r for r in records if r.get("label") is not None]
    if not labeled:
        return 0.7  # default prior
    recent = labeled[-recent_n:]
    successes = sum(1 for r in recent if r["label"] == 1)
    return successes / len(recent)


def get_training_data() -> tuple[list[dict], list[int]]:
    """
    Returns (X_features, y_labels) for all labeled sessions across all models.
    Excludes neutral ratings (label=None).
    Ready for: sklearn LogisticRegression().fit(X, y)
    """
    records = load_feedback()
    labeled = [r for r in records if r.get("label") is not None]

    all_models = list({r["model"] for r in labeled})
    model_enc = {m: i for i, m in enumerate(sorted(all_models))}

    X = []
    y = []
    for r in labeled:
        bd = r.get("breakdown", {})
        vals = list(bd.values())
        X.append({
            "time_score": vals[0] if len(vals) > 0 else 0,
            "latency_score": vals[1] if len(vals) > 1 else 0,
            "error_score": vals[2] if len(vals) > 2 else 0,
            "context_score": vals[3] if len(vals) > 3 else 0,
            "volatility_score": vals[4] if len(vals) > 4 else 0,
            "btc_change_abs": r.get("btc_change_abs", 0),
            "eth_change_abs": r.get("eth_change_abs", 0),
            "hour_utc": r.get("hour_utc", 12),
            "day_of_week": r.get("day_of_week", 0),
            "model_encoded": model_enc.get(r["model"], 0),
        })
        y.append(r["label"])

    return X, y


def training_data_summary() -> dict:
    records = load_feedback()
    labeled = [r for r in records if r.get("label") is not None]
    return {
        "total_sessions": len(records),
        "labeled": len(labeled),
        "positive": sum(1 for r in labeled if r["label"] == 1),
        "negative": sum(1 for r in labeled if r["label"] == 0),
        "models": list({r["model"] for r in records}),
        "ready_for_ml": len(labeled) >= 30,
        "note": "Call get_training_data() then sklearn LogisticRegression when ready_for_ml=True"
    }
