from __future__ import annotations

from datetime import datetime

from app.schemas import ForecastNextTicketOut, ForecastOptionOut
from app.services.address_model import predict_address_service
from app.services.reason_forecast import predict_reason_forecast_service


def _infer_season(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def _reason_label(reason_code: str) -> str:
    labels = {
        "water_leak": "протечка воды",
        "heating": "проблема с отоплением",
        "electricity": "проблема с электричеством",
        "garbage": "вывоз мусора",
        "sewer": "проблема с канализацией",
        "elevator": "неисправность лифта",
        "roof": "проблема с кровлей",
        "yard": "проблема с дворовой территорией",
    }
    return labels.get(reason_code, reason_code)


def forecast_next_ticket_service() -> ForecastNextTicketOut:
    now = datetime.utcnow()
    month = now.month
    hour = now.hour
    season = _infer_season(month)

    reason_predictions = predict_reason_forecast_service(
        season=season,
        month=month,
        hour=hour,
        top_k=3,
    )

    top_predictions: list[ForecastOptionOut] = []
    for reason_prediction in reason_predictions:
        address_predictions = predict_address_service(
            reason_category=str(reason_prediction["reason"]),
            season=season,
            month=month,
            hour=hour,
            top_k=3,
        )
        for address_prediction in address_predictions:
            combined_score = round(
                float(reason_prediction["probability"]) * float(address_prediction.probability),
                4,
            )
            top_predictions.append(
                ForecastOptionOut(
                    reason=str(reason_prediction["reason"]),
                    reason_probability=float(reason_prediction["probability"]),
                    address=address_prediction,
                    combined_score=combined_score,
                )
            )

    top_predictions.sort(key=lambda item: item.combined_score, reverse=True)
    best = top_predictions[0]
    summary = (
        f"Вероятнее всего следующая заявка поступит с адреса "
        f"ул. {best.address.street}, {best.address.house_number}. "
        f"Возможная причина: {_reason_label(best.reason)}."
    )

    return ForecastNextTicketOut(
        generated_at=now,
        season=season,
        month=month,
        hour=hour,
        summary=summary,
        predicted_reason=best.reason,
        reason_confidence=best.reason_probability,
        predicted_address=best.address,
    )
