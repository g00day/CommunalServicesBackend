from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


BASE_DIR = Path(__file__).resolve().parent
MODEL_PATH = BASE_DIR / "models" / "reason_classifier.joblib"
REPORT_PATH = BASE_DIR / "artifacts" / "reason_classifier_report.txt"

FEATURE_COLUMNS = ["title", "description", "season", "month", "hour"]
TARGET_COLUMN = "reason_category"


def _resolve_dataset_path() -> Path:
    candidates = [
        BASE_DIR / "data" / "sample" / "dataset_tickets.csv",
        BASE_DIR / "data" / "sample" / "communal_tickets_dataset.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


DATASET_PATH = _resolve_dataset_path()


@dataclass(slots=True)
class PredictionResult:
    predicted_reason: str
    confidence: float
    top_reasons: list[dict[str, float]]


def _normalize_dataset(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Excel edits sometimes duplicate the header row inside the file.
    df = df[df["title"] != "title"]
    df = df[df[TARGET_COLUMN] != TARGET_COLUMN]

    df["title"] = df["title"].fillna("").astype(str).str.strip()
    df["description"] = df["description"].fillna("").astype(str).str.strip()
    df["season"] = df["season"].fillna("unknown").astype(str).str.strip().str.lower()
    df["month"] = pd.to_numeric(df["month"], errors="coerce")
    df["hour"] = pd.to_numeric(df["hour"], errors="coerce")
    df[TARGET_COLUMN] = df[TARGET_COLUMN].fillna("").astype(str).str.strip().str.lower()

    df = df[(df["title"] != "") & (df[TARGET_COLUMN] != "")]
    return df.reset_index(drop=True)


def load_dataset(dataset_path: Path | str = DATASET_PATH) -> pd.DataFrame:
    df = pd.read_csv(dataset_path)
    return _normalize_dataset(df)


def build_reason_pipeline() -> Pipeline:
    text_preprocessor = ColumnTransformer(
        transformers=[
            ("title_tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=3000), "title"),
            ("description_tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=5000), "description"),
        ],
        remainder="drop",
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("text", text_preprocessor, ["title", "description"]),
            (
                "meta",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        ("encoder", OneHotEncoder(handle_unknown="ignore")),
                    ]
                ),
                ["season", "month", "hour"],
            ),
        ]
    )

    return Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("classifier", LogisticRegression(max_iter=2000, class_weight="balanced")),
        ]
    )


def train_reason_model(
    dataset_path: Path | str = DATASET_PATH,
    model_path: Path | str = MODEL_PATH,
    report_path: Path | str = REPORT_PATH,
) -> dict[str, Any]:
    df = load_dataset(dataset_path)
    if len(df) < 20:
        raise ValueError("Для обучения нужно хотя бы 20 размеченных заявок")

    x = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,
    )

    pipeline = build_reason_pipeline()
    pipeline.fit(x_train, y_train)

    y_pred = pipeline.predict(x_test)
    report = classification_report(y_test, y_pred, digits=4)

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


def load_trained_reason_model(model_path: Path | str = MODEL_PATH) -> dict[str, Any]:
    return joblib.load(model_path)


def predict_reason(
    title: str,
    description: str | None = None,
    season: str | None = None,
    month: int | None = None,
    hour: int | None = None,
    model_path: Path | str = MODEL_PATH,
    top_k: int = 3,
) -> PredictionResult:
    bundle = load_trained_reason_model(model_path)
    model: Pipeline = bundle["model"]

    sample = pd.DataFrame(
        [
            {
                "title": (title or "").strip(),
                "description": (description or "").strip(),
                "season": (season or "unknown").strip().lower(),
                "month": month,
                "hour": hour,
            }
        ]
    )

    probabilities = model.predict_proba(sample)[0]
    classes = model.classes_
    ranked = sorted(
        (
            {"reason": str(label), "probability": round(float(prob), 4)}
            for label, prob in zip(classes, probabilities)
        ),
        key=lambda item: item["probability"],
        reverse=True,
    )

    best = ranked[0]
    return PredictionResult(
        predicted_reason=best["reason"],
        confidence=best["probability"],
        top_reasons=ranked[: max(1, top_k)],
    )


if __name__ == "__main__":
    result = train_reason_model()
    print("Model trained")
    print(f"Dataset: {DATASET_PATH}")
    print(f"Rows: {result['rows']}")
    print(f"Labels: {', '.join(result['labels'])}")
    print(f"Model: {result['model_path']}")
    print(f"Report: {result['report_path']}")
