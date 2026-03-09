import json
import os
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
os.environ.setdefault("TF_ENABLE_ONEDNN_OPTS", "0")

import tensorflow as tf
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, f1_score, mean_squared_error, precision_score, recall_score
from sklearn.model_selection import KFold, RandomizedSearchCV, StratifiedKFold, train_test_split
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.utils.class_weight import compute_class_weight
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras import Model
from tensorflow.keras.layers import Concatenate, Dense, Dropout, Input, LSTM

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.db_connect import fetch_all, get_seeded_student_count, seed_synthetic_students
from utils.preprocessing import derive_targets, fit_static_preprocessor, transform_sequence


warnings.filterwarnings(
    "ignore",
    message=r"`sklearn\.utils\.parallel\.delayed` should be used with `sklearn\.utils\.parallel\.Parallel`.*",
    category=UserWarning,
    module=r"sklearn\.utils\.parallel",
)

tf.get_logger().setLevel("ERROR")
try:
    tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)
except Exception:
    pass


SAVE_DIR = Path("model") / "saved_model"
MODEL_PATH = SAVE_DIR / "performance_model.keras"
PREPROCESSOR_PATH = SAVE_DIR / "preprocessor.joblib"
METRICS_PATH = SAVE_DIR / "metrics.json"
FEATURE_MANIFEST_PATH = SAVE_DIR / "feature_manifest.json"
COMPARISON_CSV_PATH = SAVE_DIR / "model_comparison.csv"
SYNTHETIC_AUGMENT_ROWS = 10_000
TUNING_SAMPLE_LIMIT = 3_000
MAX_EPOCHS = 40

HYBRID_CONFIGS = [
    {
        "name": "balanced_v1",
        "static_units": (64, 32),
        "lstm_units": 32,
        "seq_dense_units": 16,
        "fused_units": 64,
        "dropout_static": 0.20,
        "dropout_fused": 0.15,
        "learning_rate": 1e-3,
        "loss_weights": {"academic_output": 0.6, "readiness_output": 1.2},
    },
    {
        "name": "readiness_focus_v2",
        "static_units": (96, 48),
        "lstm_units": 48,
        "seq_dense_units": 24,
        "fused_units": 96,
        "dropout_static": 0.18,
        "dropout_fused": 0.12,
        "learning_rate": 8e-4,
        "loss_weights": {"academic_output": 0.45, "readiness_output": 1.6},
    },
    {
        "name": "readiness_focus_v3",
        "static_units": (128, 64),
        "lstm_units": 64,
        "seq_dense_units": 32,
        "fused_units": 128,
        "dropout_static": 0.15,
        "dropout_fused": 0.10,
        "learning_rate": 7e-4,
        "loss_weights": {"academic_output": 0.35, "readiness_output": 1.8},
    },
]


def evaluate_predictions(y_ac_true, y_ac_pred, y_rd_true, y_rd_pred) -> dict:
    rmse = float(np.sqrt(mean_squared_error(y_ac_true, y_ac_pred)))
    acc = float(accuracy_score(y_rd_true, y_rd_pred))
    f1 = float(f1_score(y_rd_true, y_rd_pred, average="weighted", zero_division=0))
    precision = float(precision_score(y_rd_true, y_rd_pred, average="weighted", zero_division=0))
    recall = float(recall_score(y_rd_true, y_rd_pred, average="weighted", zero_division=0))
    return {
        "accuracy": acc,
        "f1_score": f1,
        "precision": precision,
        "recall": recall,
        "rmse": rmse,
    }


def fetch_training_dataframe() -> pd.DataFrame:
    rows = fetch_all(
        """
        SELECT
            u.id,
            u.year_of_study,
            sp.attendance_pct,
            sp.backlogs_count,
            sp.dsa_language,
            sp.coding_hours_per_week,
            sp.coding_profiles,
            sp.internships_count,
            sp.certifications_count,
            sp.projects_completed,
            sp.target_career_domain,
            sp.languages_known,
            sp.communication_rating,
            sp.stress_level,
            sp.motivation_level,
            SUM(CASE WHEN s.skill_name IS NOT NULL THEN 1 ELSE 0 END) AS skills_count,
            MAX(CASE WHEN ss.semester_no = 1 THEN ss.score END) AS S1,
            MAX(CASE WHEN ss.semester_no = 2 THEN ss.score END) AS S2,
            MAX(CASE WHEN ss.semester_no = 3 THEN ss.score END) AS S3,
            MAX(CASE WHEN ss.semester_no = 4 THEN ss.score END) AS S4,
            MAX(CASE WHEN ss.semester_no = 5 THEN ss.score END) AS S5,
            MAX(CASE WHEN ss.semester_no = 6 THEN ss.score END) AS S6,
            MAX(CASE WHEN ss.semester_no = 7 THEN ss.score END) AS S7,
            MAX(CASE WHEN ss.semester_no = 8 THEN ss.score END) AS S8
        FROM users u
        JOIN student_profiles sp ON sp.user_id = u.id
        LEFT JOIN semester_scores ss ON ss.user_id = u.id
        LEFT JOIN skills s ON s.user_id = u.id
        WHERE u.role = 'student'
        GROUP BY
            u.id, u.year_of_study, sp.attendance_pct, sp.backlogs_count,
            sp.dsa_language, sp.coding_hours_per_week, sp.internships_count,
            sp.certifications_count, sp.projects_completed, sp.target_career_domain,
            sp.communication_rating, sp.stress_level, sp.motivation_level
        """
    )

    columns = [
        "id",
        "year_of_study",
        "attendance_pct",
        "backlogs_count",
        "dsa_language",
        "coding_hours_per_week",
        "coding_profiles",
        "internships_count",
        "certifications_count",
        "projects_completed",
        "target_career_domain",
        "languages_known",
        "communication_rating",
        "stress_level",
        "motivation_level",
        "skills_count",
        "S1",
        "S2",
        "S3",
        "S4",
        "S5",
        "S6",
        "S7",
        "S8",
    ]

    df = pd.DataFrame(rows, columns=columns)
    return df


def create_synthetic_data(samples: int = 250) -> pd.DataFrame:
    rng = np.random.default_rng(42)

    df = pd.DataFrame(
        {
            "id": np.arange(1, samples + 1),
            "year_of_study": rng.integers(1, 5, size=samples),
            "attendance_pct": rng.uniform(55, 100, size=samples),
            "backlogs_count": rng.integers(0, 8, size=samples),
            "dsa_language": rng.choice(["Python", "Java", "C++"], size=samples),
            "coding_hours_per_week": rng.uniform(2, 30, size=samples),
            "coding_profiles": rng.choice(
                [
                    '{"leetcode": "", "hackerrank": "", "codechef": "", "github": ""}',
                    '{"leetcode": "http://lc.com/x", "hackerrank": "", "codechef": "", "github": ""}',
                    '{"leetcode": "http://lc.com/x", "hackerrank": "http://hr.com/x", "codechef": "", "github": "http://gh.com/x"}',
                ],
                size=samples,
            ),
            "internships_count": rng.integers(0, 4, size=samples),
            "certifications_count": rng.integers(0, 8, size=samples),
            "projects_completed": rng.integers(0, 10, size=samples),
            "target_career_domain": rng.choice(
                ["Software Development", "Data Science", "Data Analytics", "Cloud Computing"],
                size=samples,
            ),
            "languages_known": rng.choice(
                [
                    '["English"]',
                    '["English", "Hindi"]',
                    '["English", "Hindi", "Tamil"]',
                    '["English", "Hindi", "Telugu", "Kannada"]',
                ],
                size=samples,
            ),
            "communication_rating": rng.integers(2, 10, size=samples),
            "stress_level": rng.integers(1, 10, size=samples),
            "motivation_level": rng.integers(2, 10, size=samples),
            "skills_count": rng.integers(1, 12, size=samples),
        }
    )

    for i in range(1, 9):
        df[f"S{i}"] = rng.uniform(5.0, 9.8, size=samples)

    return df


def build_model(static_dim: int, config: dict, seq_len: int = 8) -> Model:
    static_input = Input(shape=(static_dim,), name="static_input")
    static_branch = Dense(config["static_units"][0], activation="relu")(static_input)
    static_branch = Dropout(config["dropout_static"])(static_branch)
    static_branch = Dense(config["static_units"][1], activation="relu")(static_branch)

    seq_input = Input(shape=(seq_len, 1), name="sequence_input")
    seq_branch = LSTM(config["lstm_units"], return_sequences=False)(seq_input)
    seq_branch = Dense(config["seq_dense_units"], activation="relu")(seq_branch)

    fused = Concatenate()([static_branch, seq_branch])
    fused = Dense(config["fused_units"], activation="relu")(fused)
    fused = Dropout(config["dropout_fused"])(fused)

    academic_output = Dense(1, activation="linear", name="academic_output")(fused)
    readiness_output = Dense(3, activation="softmax", name="readiness_output")(fused)

    model = Model(inputs=[static_input, seq_input], outputs=[academic_output, readiness_output])
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=float(config["learning_rate"])),
        loss={
            "academic_output": "mse",
            "readiness_output": "sparse_categorical_crossentropy",
        },
        loss_weights=config["loss_weights"],
        metrics={
            "academic_output": ["mae"],
            "readiness_output": ["accuracy"],
        },
    )
    return model


def train_and_save_model() -> None:
    db_seed_added = 0
    try:
        existing_seeded = get_seeded_student_count()
        if existing_seeded < SYNTHETIC_AUGMENT_ROWS:
            to_add = SYNTHETIC_AUGMENT_ROWS - existing_seeded
            seed_info = seed_synthetic_students(total_rows=to_add)
            db_seed_added = int(seed_info.get("inserted", 0))
            print(f"Synthetic DB seed -> requested: {to_add}, inserted: {db_seed_added}")
        else:
            print(f"Synthetic DB seed already present: {existing_seeded} rows")
    except Exception as exc:
        print(f"DB synthetic seeding skipped: {exc}")

    try:
        df = fetch_training_dataframe()
    except Exception as exc:
        print(f"Database fetch failed ({exc}). Using synthetic dataset for bootstrap training.")
        df = create_synthetic_data(samples=300)

    if len(df) < 40:
        print("Insufficient DB rows for robust training. Using synthetic dataset for bootstrap training.")
        df = create_synthetic_data(samples=300)

    if db_seed_added == 0 and len(df) < SYNTHETIC_AUGMENT_ROWS:
        base_rows = int(len(df))
        synthetic_df = create_synthetic_data(samples=SYNTHETIC_AUGMENT_ROWS)
        synthetic_df["id"] = np.arange(base_rows + 1, base_rows + SYNTHETIC_AUGMENT_ROWS + 1)
        df = pd.concat([df, synthetic_df], ignore_index=True)
        print(f"Training rows -> base: {base_rows}, synthetic_added_in_memory: {SYNTHETIC_AUGMENT_ROWS}, total: {len(df)}")
    else:
        print(f"Training rows from DB total: {len(df)}")

    academic_target, readiness_target = derive_targets(df)
    static_arr, artifacts = fit_static_preprocessor(df)
    seq_arr = transform_sequence(df, artifacts)

    X_static_train, X_static_test, X_seq_train, X_seq_test, y_ac_train, y_ac_test, y_rd_train, y_rd_test = train_test_split(
        static_arr,
        seq_arr,
        academic_target,
        readiness_target,
        test_size=0.2,
        random_state=42,
        stratify=readiness_target,
    )

    class_labels = np.unique(y_rd_train)
    class_weights_arr = compute_class_weight(class_weight="balanced", classes=class_labels, y=y_rd_train)
    class_weights = {int(label): float(weight) for label, weight in zip(class_labels, class_weights_arr)}

    best_model = None
    best_hybrid_config = None
    best_val_readiness_acc = -1.0
    best_epochs_ran = 0

    for hybrid_config in HYBRID_CONFIGS:
        tf.keras.backend.clear_session()
        model_candidate = build_model(static_dim=X_static_train.shape[1], config=hybrid_config, seq_len=X_seq_train.shape[1])

        callbacks = [
            EarlyStopping(
                monitor="val_readiness_output_accuracy",
                mode="max",
                patience=6,
                restore_best_weights=True,
                verbose=0,
            ),
            ReduceLROnPlateau(
                monitor="val_loss",
                factor=0.5,
                patience=3,
                min_lr=1e-5,
                verbose=0,
            ),
        ]

        history = model_candidate.fit(
            [X_static_train, X_seq_train],
            {"academic_output": y_ac_train, "readiness_output": y_rd_train},
            validation_split=0.2,
            epochs=MAX_EPOCHS,
            batch_size=16,
            callbacks=callbacks,
            verbose=0,
        )

        val_acc_series = history.history.get("val_readiness_output_accuracy", [])
        candidate_val_acc = float(max(val_acc_series)) if val_acc_series else 0.0
        candidate_epochs = len(history.history.get("loss", []))
        print(
            f"Hybrid config {hybrid_config['name']} -> best val readiness acc: {candidate_val_acc:.4f}, epochs: {candidate_epochs}"
        )

        if candidate_val_acc > best_val_readiness_acc:
            best_val_readiness_acc = candidate_val_acc
            best_model = model_candidate
            best_hybrid_config = hybrid_config
            best_epochs_ran = candidate_epochs

    model = best_model

    pred_academic, pred_readiness_proba = model.predict([X_static_test, X_seq_test], verbose=0)
    pred_readiness = np.argmax(pred_readiness_proba, axis=1)

    hybrid_metrics = evaluate_predictions(
        y_ac_test,
        pred_academic.flatten(),
        y_rd_test,
        pred_readiness,
    )

    X_flat = np.hstack([static_arr, seq_arr.reshape((seq_arr.shape[0], -1))]).astype("float32")
    X_flat_train, X_flat_test, y_ac_train_flat, y_ac_test_flat, y_rd_train_flat, y_rd_test_flat = train_test_split(
        X_flat,
        academic_target,
        readiness_target,
        test_size=0.2,
        random_state=42,
        stratify=readiness_target,
    )

    tune_rows = min(TUNING_SAMPLE_LIMIT, X_flat_train.shape[0])
    tune_indices = np.random.choice(X_flat_train.shape[0], size=tune_rows, replace=False)
    X_flat_tune = X_flat_train[tune_indices]
    y_ac_tune = y_ac_train_flat[tune_indices]
    y_rd_tune = y_rd_train_flat[tune_indices]

    cv_cls = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_reg = KFold(n_splits=5, shuffle=True, random_state=42)

    dt_clf_search = RandomizedSearchCV(
        estimator=DecisionTreeClassifier(random_state=42),
        param_distributions={
            "max_depth": [4, 6, 8, 10, 12, None],
            "min_samples_split": [2, 4, 8, 12],
            "min_samples_leaf": [1, 2, 4, 6],
            "criterion": ["gini", "entropy"],
            "class_weight": [None, "balanced"],
        },
        n_iter=12,
        scoring="f1_weighted",
        cv=cv_cls,
        n_jobs=-1,
        random_state=42,
        refit=True,
    )
    dt_reg_search = RandomizedSearchCV(
        estimator=DecisionTreeRegressor(random_state=42),
        param_distributions={
            "max_depth": [4, 6, 8, 10, 12, None],
            "min_samples_split": [2, 4, 8, 12],
            "min_samples_leaf": [1, 2, 4, 6],
            "criterion": ["squared_error", "absolute_error", "friedman_mse"],
        },
        n_iter=12,
        scoring="neg_root_mean_squared_error",
        cv=cv_reg,
        n_jobs=-1,
        random_state=42,
        refit=True,
    )
    dt_clf_search.fit(X_flat_tune, y_rd_tune)
    dt_reg_search.fit(X_flat_tune, y_ac_tune)
    dt_clf = DecisionTreeClassifier(random_state=42, **dt_clf_search.best_params_)
    dt_reg = DecisionTreeRegressor(random_state=42, **dt_reg_search.best_params_)
    dt_clf.fit(X_flat_train, y_rd_train_flat)
    dt_reg.fit(X_flat_train, y_ac_train_flat)

    dt_ac_pred = dt_reg.predict(X_flat_test)
    dt_rd_pred = dt_clf.predict(X_flat_test)
    dt_metrics = evaluate_predictions(y_ac_test_flat, dt_ac_pred, y_rd_test_flat, dt_rd_pred)

    rf_clf_search = RandomizedSearchCV(
        estimator=RandomForestClassifier(random_state=42, n_jobs=-1),
        param_distributions={
            "n_estimators": [200, 300, 400, 500],
            "max_depth": [None, 8, 12, 16],
            "min_samples_split": [2, 4, 8],
            "min_samples_leaf": [1, 2, 4],
            "max_features": ["sqrt", "log2", None],
            "class_weight": [None, "balanced"],
        },
        n_iter=14,
        scoring="f1_weighted",
        cv=cv_cls,
        n_jobs=-1,
        random_state=42,
        refit=True,
    )
    rf_reg_search = RandomizedSearchCV(
        estimator=RandomForestRegressor(random_state=42, n_jobs=-1),
        param_distributions={
            "n_estimators": [200, 300, 400, 500],
            "max_depth": [None, 8, 12, 16],
            "min_samples_split": [2, 4, 8],
            "min_samples_leaf": [1, 2, 4],
            "max_features": ["sqrt", "log2", None],
        },
        n_iter=14,
        scoring="neg_root_mean_squared_error",
        cv=cv_reg,
        n_jobs=-1,
        random_state=42,
        refit=True,
    )
    rf_clf_search.fit(X_flat_tune, y_rd_tune)
    rf_reg_search.fit(X_flat_tune, y_ac_tune)
    rf_clf = RandomForestClassifier(random_state=42, n_jobs=-1, **rf_clf_search.best_params_)
    rf_reg = RandomForestRegressor(random_state=42, n_jobs=-1, **rf_reg_search.best_params_)
    rf_clf.fit(X_flat_train, y_rd_train_flat)
    rf_reg.fit(X_flat_train, y_ac_train_flat)

    rf_ac_pred = rf_reg.predict(X_flat_test)
    rf_rd_pred = rf_clf.predict(X_flat_test)
    rf_metrics = evaluate_predictions(y_ac_test_flat, rf_ac_pred, y_rd_test_flat, rf_rd_pred)

    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    model.save(MODEL_PATH)
    joblib.dump(artifacts, PREPROCESSOR_PATH)

    metrics = {
        "feature_branches": {
            "feature_groups": {
                "academic": ["year_of_study", "attendance_pct", "backlogs_count", "S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"],
                "skill_based": ["skills_count", "dsa_language", "coding_hours_per_week", "coding_profiles_count"],
                "career_oriented": ["internships_count", "certifications_count", "projects_completed", "target_career_domain", "languages_known_count"],
                "behavioral": ["communication_rating", "stress_level", "motivation_level"],
            },
            "lstm_sequence_features": ["S1", "S2", "S3", "S4", "S5", "S6", "S7", "S8"],
            "dnn_static_features": [
                "year_of_study",
                "attendance_pct",
                "backlogs_count",
                "skills_count",
                "dsa_language",
                "coding_hours_per_week",
                "coding_profiles_count",
                "internships_count",
                "certifications_count",
                "projects_completed",
                "target_career_domain",
                "languages_known_count",
                "communication_rating",
                "stress_level",
                "motivation_level",
            ],
            "total_raw_features_used": 23,
        },
        "hybrid_dnn_lstm": hybrid_metrics,
        "decision_tree": dt_metrics,
        "random_forest": rf_metrics,
        "tuning": {
            "decision_tree": {
                "classifier_best_params": dt_clf_search.best_params_,
                "classifier_cv_f1_weighted": float(dt_clf_search.best_score_),
                "regressor_best_params": dt_reg_search.best_params_,
                "regressor_cv_neg_rmse": float(dt_reg_search.best_score_),
            },
            "random_forest": {
                "classifier_best_params": rf_clf_search.best_params_,
                "classifier_cv_f1_weighted": float(rf_clf_search.best_score_),
                "regressor_best_params": rf_reg_search.best_params_,
                "regressor_cv_neg_rmse": float(rf_reg_search.best_score_),
            },
            "hybrid_dnn_lstm": {
                "epochs_max": MAX_EPOCHS,
                "epochs_ran_best_config": best_epochs_ran,
                "batch_size": 16,
                "class_weights": class_weights,
                "sample_weights_used": False,
                "callbacks": ["EarlyStopping", "ReduceLROnPlateau"],
                "selected_config": best_hybrid_config,
                "best_val_readiness_accuracy": best_val_readiness_acc,
            },
        },
        "accuracy": hybrid_metrics["accuracy"],
        "f1_score": hybrid_metrics["f1_score"],
        "precision": hybrid_metrics["precision"],
        "recall": hybrid_metrics["recall"],
        "rmse": hybrid_metrics["rmse"],
        "dataset_size": int(len(df)),
    }

    with open(METRICS_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    with open(FEATURE_MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(metrics["feature_branches"], f, indent=2)

    comparison_df = pd.DataFrame(
        [
            {
                "model": "hybrid_dnn_lstm",
                **hybrid_metrics,
            },
            {
                "model": "decision_tree",
                "best_clf_params": json.dumps(dt_clf_search.best_params_),
                "best_reg_params": json.dumps(dt_reg_search.best_params_),
                **dt_metrics,
            },
            {
                "model": "random_forest",
                "best_clf_params": json.dumps(rf_clf_search.best_params_),
                "best_reg_params": json.dumps(rf_reg_search.best_params_),
                **rf_metrics,
            },
        ]
    )
    comparison_df.to_csv(COMPARISON_CSV_PATH, index=False)

    print("Model and preprocessor saved successfully.")
    print(f"Feature manifest saved at: {FEATURE_MANIFEST_PATH}")
    print(f"Comparison CSV saved at: {COMPARISON_CSV_PATH}")
    print("\n===== MODEL COMPARISON (Paper Benchmarks) =====")
    print(f"Dataset size: {len(df)}")
    print(f"Hybrid DNN+LSTM -> ACC: {hybrid_metrics['accuracy']:.4f}, F1: {hybrid_metrics['f1_score']:.4f}, Precision: {hybrid_metrics['precision']:.4f}, Recall: {hybrid_metrics['recall']:.4f}, RMSE: {hybrid_metrics['rmse']:.4f}")
    print(f"Decision Tree  -> ACC: {dt_metrics['accuracy']:.4f}, F1: {dt_metrics['f1_score']:.4f}, Precision: {dt_metrics['precision']:.4f}, Recall: {dt_metrics['recall']:.4f}, RMSE: {dt_metrics['rmse']:.4f}")
    print(f"Random Forest  -> ACC: {rf_metrics['accuracy']:.4f}, F1: {rf_metrics['f1_score']:.4f}, Precision: {rf_metrics['precision']:.4f}, Recall: {rf_metrics['recall']:.4f}, RMSE: {rf_metrics['rmse']:.4f}")
    print("==============================================\n")
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    os.environ["TF_CPP_MIN_LOG_LEVEL"] = "2"
    tf.random.set_seed(42)
    np.random.seed(42)
    train_and_save_model()
