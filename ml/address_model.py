from __future__ import annotations

from dataclasses import dataclass
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
MODEL_PATH = BASE_DIR / "models" / "address_classifier.joblib"
REPORT_PATH = BASE_DIR / "artifacts" / "address_classifier_report.txt"

FEATURE_COLUMNS = ["reason_category", "season", "month", "hour"]
TARGET_COLUMN = "address_id"


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


@dataclass(slots=True)
class AddressPrediction:
    address_id: int
    street: str
    house_number: str
    district: str
    uprava: str
    probability: float


def _normalize_dataset(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df[df["reason_category"] != "reason_category"]
    df = df[df["address_id"] != "address_id"]

    for column in ("reason_category", "season", "street", "house_number", "district", "uprava"):
        df[column] = df[column].fillna("").astype(str).str.strip()

    df["reason_category"] = df["reason_category"].str.lower()
    df["season"] = df["season"].str.lower()
    df["month"] = pd.to_numeric(df["month"], errors="coerce")
    df["hour"] = pd.to_numeric(df["hour"], errors="coerce")
    df["address_id"] = pd.to_numeric(df["address_id"], errors="coerce")

    df = df[
        (df["reason_category"] != "")
        & df["address_id"].notna()
        & (df["street"] != "")
        & (df["house_number"] != "")
    ]
    df["address_id"] = df["address_id"].astype(int)
    return df.reset_index(drop=True)


def load_dataset(dataset_path: Path | str = DATASET_PATH) -> pd.DataFrame:
    return _normalize_dataset(pd.read_csv(dataset_path))


def build_address_pipeline() -> Pipeline:
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


def train_address_model(
    dataset_path: Path | str = DATASET_PATH,
    model_path: Path | str = MODEL_PATH,
    report_path: Path | str = REPORT_PATH,
) -> dict[str, Any]:
    df = load_dataset(dataset_path)
    if len(df) < 20:
        raise ValueError("Для обучения модели адреса нужно хотя бы 20 заявок")

    x = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    stratify_target = y if y.value_counts().min() >= 2 else None
    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
        stratify=stratify_target,
    )

    pipeline = build_address_pipeline()
    pipeline.fit(x_train, y_train)

    y_pred = pipeline.predict(x_test)
    report = classification_report(y_test, y_pred, digits=4, zero_division=0)

    address_lookup = (
        df[["address_id", "street", "house_number", "district", "uprava"]]
        .drop_duplicates(subset=["address_id"])
        .set_index("address_id")
        .to_dict(orient="index")
    )

    model_path = Path(model_path)
    report_path = Path(report_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    joblib.dump(
        {
            "model": pipeline,
            "feature_columns": FEATURE_COLUMNS,
            "target_column": TARGET_COLUMN,
            "address_lookup": address_lookup,
        },
        model_path,
    )
    report_path.write_text(report, encoding="utf-8")

    return {
        "rows": len(df),
        "train_rows": len(x_train),
        "test_rows": len(x_test),
        "unique_addresses": int(df["address_id"].nunique()),
        "model_path": str(model_path),
        "report_path": str(report_path),
    }


def load_trained_address_model(model_path: Path | str = MODEL_PATH) -> dict[str, Any]:
    return joblib.load(model_path)


def predict_address(
    reason_category: str,
    season: str,
    month: int,
    hour: int,
    model_path: Path | str = MODEL_PATH,
    top_k: int = 3,
) -> list[AddressPrediction]:
    bundle = load_trained_address_model(model_path)
    model: Pipeline = bundle["model"]
    address_lookup: dict[int, dict[str, str]] = bundle["address_lookup"]

    sample = pd.DataFrame(
        [
            {
                "reason_category": (reason_category or "").strip().lower(),
                "season": (season or "").strip().lower(),
                "month": month,
                "hour": hour,
            }
        ]
    )

    probabilities = model.predict_proba(sample)[0]
    classes = model.classes_
    ranked = sorted(
        zip(classes, probabilities),
        key=lambda item: float(item[1]),
        reverse=True,
    )[: max(1, top_k)]

    predictions: list[AddressPrediction] = []
    for address_id, probability in ranked:
        address_id_int = int(address_id)
        metadata = address_lookup.get(address_id_int, {})
        predictions.append(
            AddressPrediction(
                address_id=address_id_int,
                street=str(metadata.get("street", "")),
                house_number=str(metadata.get("house_number", "")),
                district=str(metadata.get("district", "")),
                uprava=str(metadata.get("uprava", "")),
                probability=round(float(probability), 4),
            )
        )
    return predictions


if __name__ == "__main__":
    result = train_address_model()
    print("Address model trained")
    print(f"Dataset: {DATASET_PATH}")
    print(f"Rows: {result['rows']}")
    print(f"Unique addresses: {result['unique_addresses']}")
    print(f"Model: {result['model_path']}")
    print(f"Report: {result['report_path']}")
