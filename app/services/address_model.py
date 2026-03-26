from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from fastapi import HTTPException
from sklearn.pipeline import Pipeline

from app.schemas import ForecastAddressOut


MODEL_PATH = Path(__file__).resolve().parents[2] / "ml" / "models" / "address_classifier.joblib"


def _infer_season(month: int | None) -> str:
    if month is None:
        month = datetime.utcnow().month
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


@lru_cache(maxsize=1)
def _load_model_bundle() -> dict[str, Any]:
    if not MODEL_PATH.exists():
        from ml.address_model import train_address_model

        try:
            train_address_model()
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Не удалось обучить модель адреса: {exc}",
            ) from exc
    if not MODEL_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Файл модели адреса не найден: {MODEL_PATH}")
    return joblib.load(MODEL_PATH)


def clear_address_model_cache() -> None:
    _load_model_bundle.cache_clear()


def predict_address_service(
    reason_category: str,
    season: str | None = None,
    month: int | None = None,
    hour: int | None = None,
    top_k: int = 3,
) -> list[ForecastAddressOut]:
    bundle = _load_model_bundle()
    model: Pipeline = bundle["model"]
    address_lookup: dict[int, dict[str, str]] = bundle["address_lookup"]

    season_value = (season or _infer_season(month)).strip().lower()
    month_value = month if month is not None else datetime.utcnow().month
    hour_value = hour if hour is not None else datetime.utcnow().hour

    sample = pd.DataFrame(
        [
            {
                "reason_category": reason_category.strip().lower(),
                "season": season_value,
                "month": month_value,
                "hour": hour_value,
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

    predictions: list[ForecastAddressOut] = []
    for address_id, probability in ranked:
        address_id_int = int(address_id)
        metadata = address_lookup.get(address_id_int, {})
        predictions.append(
            ForecastAddressOut(
                address_id=address_id_int,
                street=str(metadata.get("street", "")),
                house_number=str(metadata.get("house_number", "")),
                district=str(metadata.get("district", "")),
                uprava=str(metadata.get("uprava", "")),
                probability=round(float(probability), 4),
            )
        )
    return predictions
