from __future__ import annotations

from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "reason_forecast.joblib"
REPORT_PATH = BASE_DIR / "artifacts" / "reason_forecast_report.txt"

FEATURE_COLUMNS = ["season", "month", "hour"]
TARGET_COLUMN = "reason_category"


def _resolve_dataset_path() -> Path:
    candidates = [
        BASE_DIR / "data" / "generated" / "address_training_dataset.csv",
        BASE_DIR / "data" / "sample" / "dataset_tickets.csv",
        BASE_DIR / "data" / "sample" / "communal_tickets_dataset.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


DATASET_PATH = _resolve_dataset_path()


def _normalize_dataset(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df[df["reason_category"] != "reason_category"]
    for column in ("reason_category", "season"):
        df[column] = df[column].fillna("").astype(str).str.strip().str.lower()
    df["month"] = pd.to_numeric(df["month"], errors="coerce")
    df["hour"] = pd.to_numeric(df["hour"], errors="coerce")
    df = df[(df["reason_category"] != "") & (df["season"] != "")]
    return df.reset_index(drop=True)


def load_dataset(dataset_path: Path | str = DATASET_PATH) -> pd.DataFrame:
    return _normalize_dataset(pd.read_csv(dataset_path))


def build_reason_forecast_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "meta",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                FEATURE_COLUMNS,
            )
        ]
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", LogisticRegression(max_iter=3000, class_weight="balanced")),
        ]
    )


def train_reason_forecast_model(
    dataset_path: Path | str = DATASET_PATH,
    model_path: Path | str = MODEL_PATH,
    report_path: Path | str = REPORT_PATH,
) -> dict[str, Any]:
    df = load_dataset(dataset_path)
    if len(df) < 20:
        raise ValueError("Для обучения прогноза причин нужно хотя бы 20 заявок")

    x = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    pipeline = build_reason_forecast_pipeline()
    pipeline.fit(x_train, y_train)

    y_pred = pipeline.predict(x_test)
    report = classification_report(y_test, y_pred, digits=4, zero_division=0)

    model_path = Path(model_path)
    report_path = Path(report_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump(
        {
            "model": pipeline,
            "feature_columns": FEATURE_COLUMNS,
            "target_column": TARGET_COLUMN,
            "labels": sorted(y.unique().tolist()),
        },
        model_path,
    )
    report_path.write_text(report, encoding="utf-8")

    return {
        "rows": len(df),
        "train_rows": len(x_train),
        "test_rows": len(x_test),
        "labels": sorted(y.unique().tolist()),
        "model_path": str(model_path),
        "report_path": str(report_path),
    }


if __name__ == "__main__":
    result = train_reason_forecast_model()
    print("Reason forecast model trained")
    print(f"Dataset: {DATASET_PATH}")
    print(f"Rows: {result['rows']}")
    print(f"Labels: {', '.join(result['labels'])}")
    print(f"Model: {result['model_path']}")
    print(f"Report: {result['report_path']}")
