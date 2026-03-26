from __future__ import annotations

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from fastapi import HTTPException
from sklearn.pipeline import Pipeline


MODEL_PATH = Path(__file__).resolve().parents[2] / "ml" / "models" / "reason_forecast.joblib"


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
        from ml.reason_forecast_model import train_reason_forecast_model

        try:
            train_reason_forecast_model()
        except Exception as exc:
            raise HTTPException(
                status_code=500,
                detail=f"Не удалось обучить модель прогноза причин: {exc}",
            ) from exc
    if not MODEL_PATH.exists():
        raise HTTPException(status_code=500, detail=f"Файл модели причин не найден: {MODEL_PATH}")
    return joblib.load(MODEL_PATH)


def clear_reason_forecast_cache() -> None:
    _load_model_bundle.cache_clear()


def predict_reason_forecast_service(
    season: str | None = None,
    month: int | None = None,
    hour: int | None = None,
    top_k: int = 3,
) -> list[dict[str, float | str]]:
    bundle = _load_model_bundle()
    model: Pipeline = bundle["model"]

    month_value = month if month is not None else datetime.utcnow().month
    hour_value = hour if hour is not None else datetime.utcnow().hour
    season_value = (season or _infer_season(month_value)).strip().lower()

    sample = pd.DataFrame(
        [
            {
                "season": season_value,
                "month": month_value,
                "hour": hour_value,
            }
        ]
    )

    probabilities = model.predict_proba(sample)[0]
    classes = model.classes_
    return sorted(
        (
            {"reason": str(label), "probability": round(float(prob), 4)}
            for label, prob in zip(classes, probabilities)
        ),
        key=lambda item: float(item["probability"]),
        reverse=True,
    )[: max(1, top_k)]
