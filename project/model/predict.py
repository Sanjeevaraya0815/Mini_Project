import json
import os
import sys
from pathlib import Path
from typing import Dict, Tuple

import joblib
import numpy as np

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

import tensorflow as tf

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.db_connect import (
    fetch_latest_prediction,
    fetch_one,
    get_profile_bundle,
    save_prediction,
)
from utils.preprocessing import single_row_from_bundle, transform_sequence, transform_static


SAVE_DIR = Path("model") / "saved_model"
MODEL_PATH = SAVE_DIR / "performance_model.keras"
PREPROCESSOR_PATH = SAVE_DIR / "preprocessor.joblib"

READINESS_LABELS = {0: "Low", 1: "Medium", 2: "High"}

FEATURE_IMPACT_WEIGHTS = {
    "attendance_pct": 1.0,
    "backlogs_count": -1.3,
    "coding_hours_per_week": 0.8,
    "internships_count": 1.2,
    "certifications_count": 0.9,
    "projects_completed": 0.9,
    "communication_rating": 0.7,
    "stress_level": -0.7,
    "motivation_level": 0.8,
    "skills_count": 0.6,
}


def _load_model_assets():
    if not MODEL_PATH.exists() or not PREPROCESSOR_PATH.exists():
        raise FileNotFoundError("Saved model artifacts not found. Run model/train_model.py first.")

    model = tf.keras.models.load_model(MODEL_PATH)
    artifacts = joblib.load(PREPROCESSOR_PATH)
    return model, artifacts


def _compute_feature_importance(row_dict: Dict) -> Dict[str, Dict[str, float]]:
    raw_scores = {}
    for key, weight in FEATURE_IMPACT_WEIGHTS.items():
        value = float(row_dict.get(key, 0))
        raw_scores[key] = value * weight

    sorted_items = sorted(raw_scores.items(), key=lambda x: x[1], reverse=True)
    helping = dict(sorted_items[:5])
    hurting = dict(sorted(raw_scores.items(), key=lambda x: x[1])[:5])

    return {
        "helping": {k: round(v, 3) for k, v in helping.items()},
        "hurting": {k: round(v, 3) for k, v in hurting.items()},
    }


def predict_for_user(user_id: int, persist: bool = True) -> Tuple[float, str, Dict]:
    model, artifacts = _load_model_assets()

    user_row = fetch_one(
        "SELECT id, year_of_study FROM users WHERE id = %s AND role = 'student'",
        (user_id,),
    )
    if not user_row:
        raise ValueError("Student user not found.")

    profile_bundle = get_profile_bundle(user_id)
    row_df = single_row_from_bundle(
        {
            "id": user_row[0],
            "year_of_study": user_row[1],
        },
        profile_bundle,
    )

    static_arr = np.asarray(transform_static(row_df, artifacts), dtype="float32")
    seq_arr = np.asarray(transform_sequence(row_df, artifacts), dtype="float32")

    academic_pred, readiness_proba = model.predict([static_arr, seq_arr], verbose=0)
    academic_score = float(np.clip(academic_pred.flatten()[0], 0, 100))
    readiness_idx = int(np.argmax(readiness_proba, axis=1)[0])
    readiness_label = READINESS_LABELS[readiness_idx]

    feature_importance = _compute_feature_importance(row_df.iloc[0].to_dict())

    if persist:
        save_prediction(
            user_id=user_id,
            academic_score=academic_score,
            placement_readiness=readiness_label,
            feature_importance_json=json.dumps(feature_importance),
            model_version="v1",
        )

    return academic_score, readiness_label, feature_importance


def get_latest_or_predict(user_id: int) -> Dict:
    latest = fetch_latest_prediction(user_id)
    if latest:
        fi = latest["feature_importance"]
        if isinstance(fi, str):
            try:
                fi = json.loads(fi)
            except json.JSONDecodeError:
                fi = {}
        latest["feature_importance"] = fi
        return latest

    academic_score, readiness, feature_importance = predict_for_user(user_id, persist=True)
    return {
        "academic_score": academic_score,
        "placement_readiness": readiness,
        "feature_importance": feature_importance,
        "created_at": None,
    }
