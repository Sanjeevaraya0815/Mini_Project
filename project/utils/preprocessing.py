import json
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler


NUMERIC_COLS = [
    "attendance_pct",
    "backlogs_count",
    "coding_hours_per_week",
    "coding_profiles_count",
    "internships_count",
    "certifications_count",
    "projects_completed",
    "languages_known_count",
    "communication_rating",
    "stress_level",
    "motivation_level",
    "skills_count",
]

CATEGORICAL_COLS = ["year_of_study", "dsa_language", "target_career_domain"]
SEM_COLS = [f"S{i}" for i in range(1, 9)]


def _safe_count_from_json(raw_value, expected_type: str) -> int:
    if raw_value is None:
        return 0
    if isinstance(raw_value, (list, tuple)):
        return len(raw_value)
    if isinstance(raw_value, dict):
        if expected_type == "dict_non_empty_values":
            return sum(1 for value in raw_value.values() if str(value).strip())
        return len(raw_value)

    text = str(raw_value).strip()
    if not text:
        return 0

    try:
        loaded = json.loads(text)
    except json.JSONDecodeError:
        return 0

    if isinstance(loaded, list):
        return len(loaded)
    if isinstance(loaded, dict):
        if expected_type == "dict_non_empty_values":
            return sum(1 for value in loaded.values() if str(value).strip())
        return len(loaded)
    return 0


def _prepare_base_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    if "coding_profiles_count" not in df:
        raw_col = df["coding_profiles"] if "coding_profiles" in df else pd.Series([None] * len(df))
        df["coding_profiles_count"] = raw_col.apply(lambda x: _safe_count_from_json(x, "dict_non_empty_values"))

    if "languages_known_count" not in df:
        raw_col = df["languages_known"] if "languages_known" in df else pd.Series([None] * len(df))
        df["languages_known_count"] = raw_col.apply(lambda x: _safe_count_from_json(x, "list"))

    for col in NUMERIC_COLS:
        if col not in df:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    if "year_of_study" not in df:
        df["year_of_study"] = 1
    df["year_of_study"] = pd.to_numeric(df["year_of_study"], errors="coerce").fillna(1).astype(int).astype(str)

    for col in ["dsa_language", "target_career_domain"]:
        if col not in df:
            df[col] = "Unknown"
        df[col] = df[col].fillna("Unknown").astype(str)

    for col in SEM_COLS:
        if col not in df:
            df[col] = 0
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    return df


def fit_static_preprocessor(df: pd.DataFrame) -> Tuple[np.ndarray, Dict]:
    df = _prepare_base_dataframe(df)

    scaler = StandardScaler()
    numeric_arr = scaler.fit_transform(df[NUMERIC_COLS])

    cat_df = pd.get_dummies(df[CATEGORICAL_COLS], prefix=CATEGORICAL_COLS)
    cat_columns = cat_df.columns.tolist()

    static_arr = np.hstack([numeric_arr, cat_df.values]).astype("float32")

    artifacts = {
        "scaler": scaler,
        "numeric_cols": NUMERIC_COLS,
        "categorical_cols": CATEGORICAL_COLS,
        "cat_columns": cat_columns,
        "sem_cols": SEM_COLS,
    }
    return static_arr, artifacts


def transform_static(df: pd.DataFrame, artifacts: Dict) -> np.ndarray:
    df = _prepare_base_dataframe(df)

    numeric_arr = artifacts["scaler"].transform(df[artifacts["numeric_cols"]])
    cat_df = pd.get_dummies(df[artifacts["categorical_cols"]], prefix=artifacts["categorical_cols"])
    cat_df = cat_df.reindex(columns=artifacts["cat_columns"], fill_value=0)

    return np.hstack([numeric_arr, cat_df.values]).astype("float32")


def transform_sequence(df: pd.DataFrame, artifacts: Dict) -> np.ndarray:
    df = _prepare_base_dataframe(df)
    seq = df[artifacts["sem_cols"]].values.astype("float32")
    return seq.reshape((-1, len(artifacts["sem_cols"]), 1))


def derive_targets(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    df = _prepare_base_dataframe(df)

    sem_avg = df[SEM_COLS].mean(axis=1) * 10.0
    academic_score = (
        sem_avg * 0.55
        + df["attendance_pct"] * 0.15
        + (10 - df["backlogs_count"].clip(0, 10)) * 2.0
        + df["coding_hours_per_week"].clip(0, 40) * 0.4
        + df["coding_profiles_count"].clip(0, 8) * 0.8
        + df["internships_count"].clip(0, 5) * 2.0
        + df["certifications_count"].clip(0, 8) * 1.25
        + df["projects_completed"].clip(0, 10) * 1.2
        + df["languages_known_count"].clip(0, 6) * 0.6
        + df["communication_rating"] * 1.2
        + df["motivation_level"] * 1.3
        - df["stress_level"] * 0.8
    )
    academic_score = np.clip(academic_score, 0, 100).values.astype("float32")

    readiness_score = (
        academic_score * 0.35
        + df["internships_count"] * 8
        + df["certifications_count"] * 4
        + df["projects_completed"] * 3
        + df["coding_profiles_count"] * 2
        + df["languages_known_count"] * 1.2
        + df["communication_rating"] * 3
        + df["motivation_level"] * 2
        - df["backlogs_count"] * 4
        - df["stress_level"] * 2
    )

    readiness_class = np.where(
        readiness_score >= 70,
        2,
        np.where(readiness_score >= 45, 1, 0),
    ).astype("int32")

    return academic_score, readiness_class


def single_row_from_bundle(user_row: Dict, profile_bundle: Dict) -> pd.DataFrame:
    profile = profile_bundle.get("profile")
    sem_scores = profile_bundle.get("semester_scores", [])
    skills = profile_bundle.get("skills", [])

    row = {
        "year_of_study": user_row.get("year_of_study", 1),
        "attendance_pct": profile[0] if profile else 0,
        "backlogs_count": profile[1] if profile else 0,
        "dsa_language": profile[2] if profile else "Unknown",
        "coding_hours_per_week": profile[3] if profile else 0,
        "coding_profiles_count": _safe_count_from_json(profile[4] if profile else None, "dict_non_empty_values"),
        "internships_count": profile[5] if profile else 0,
        "certifications_count": profile[6] if profile else 0,
        "projects_completed": profile[7] if profile else 0,
        "target_career_domain": profile[8] if profile else "Unknown",
        "languages_known_count": _safe_count_from_json(profile[9] if profile else None, "list"),
        "communication_rating": profile[10] if profile else 5,
        "stress_level": profile[11] if profile else 5,
        "motivation_level": profile[12] if profile else 5,
        "skills_count": len(skills),
    }

    for idx in range(8):
        row[f"S{idx + 1}"] = sem_scores[idx] if idx < len(sem_scores) else 0

    return pd.DataFrame([row])
