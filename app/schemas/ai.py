from datetime import datetime

from pydantic import BaseModel


class MlStatusOut(BaseModel):
    active_reason_classifier_path: str
    active_reason_forecast_model_path: str
    active_address_model_path: str
    generated_dataset_path: str
    reason_forecast_model_version: int
    address_model_version: int
    new_tickets_since_train: int
    retrain_threshold: int
    last_trained_at: str | None
    last_retrain_status: str
    is_retraining: bool


class ForecastAddressOut(BaseModel):
    address_id: int
    street: str
    house_number: str
    district: str
    uprava: str
    probability: float


class ForecastOptionOut(BaseModel):
    reason: str
    reason_probability: float
    address: ForecastAddressOut
    combined_score: float


class ForecastNextTicketOut(BaseModel):
    generated_at: datetime
    season: str
    month: int
    hour: int
    summary: str
    predicted_reason: str
    reason_confidence: float
    predicted_address: ForecastAddressOut
