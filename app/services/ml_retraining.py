from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.database import AsyncSessionLocal
from app.models import Address, District, Street, Ticket
from app.schemas import MlStatusOut


ML_DIR = Path(__file__).resolve().parents[2] / "ml"
STATE_PATH = ML_DIR / "artifacts" / "ml_state.json"
GENERATED_DATASET_PATH = ML_DIR / "data" / "generated" / "address_training_dataset.csv"
RETRAIN_THRESHOLD = 10
SAMPLE_DATASET_CANDIDATES = [
    ML_DIR / "data" / "sample" / "dataset_tickets.csv",
    ML_DIR / "data" / "sample" / "communal_tickets_dataset.csv",
]


def _default_state() -> dict:
    return {
        "active_reason_classifier_path": "ml/models/reason_classifier.joblib",
        "active_reason_forecast_model_path": "ml/models/reason_forecast.joblib",
        "active_address_model_path": "ml/models/address_classifier.joblib",
        "generated_dataset_path": "ml/data/generated/address_training_dataset.csv",
        "reason_forecast_model_version": 0,
        "address_model_version": 0,
        "new_tickets_since_train": 0,
        "retrain_threshold": RETRAIN_THRESHOLD,
        "last_trained_at": None,
        "last_retrain_status": "idle",
        "is_retraining": False,
    }


def load_ml_state() -> dict:
    if not STATE_PATH.exists():
        state = _default_state()
        save_ml_state(state)
        return state
    with STATE_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_ml_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with STATE_PATH.open("w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)


def get_ml_status() -> MlStatusOut:
    state = load_ml_state()
    return MlStatusOut(**state)


def register_new_ticket_for_retraining() -> bool:
    state = load_ml_state()
    state["new_tickets_since_train"] = int(state.get("new_tickets_since_train", 0)) + 1

    threshold = int(state.get("retrain_threshold", RETRAIN_THRESHOLD))
    should_retrain = state["new_tickets_since_train"] >= threshold and not state.get("is_retraining", False)
    if should_retrain:
        state["is_retraining"] = True
        state["last_retrain_status"] = "scheduled"

    save_ml_state(state)
    return should_retrain


async def _build_generated_dataset() -> Path:
    from ml.reason_model import predict_reason

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Ticket)
            .options(
                selectinload(Ticket.address)
                .selectinload(Address.street)
                .selectinload(Street.district)
                .selectinload(District.uprava)
            )
            .order_by(Ticket.opened_at.asc())
        )
        tickets = result.scalars().all()

    rows: list[dict] = []
    for ticket in tickets:
        address = ticket.address
        street = address.street if address else None
        district = street.district if street else None
        uprava = district.uprava if district else None
        if not address or not street or not district:
            continue

        opened_at = ticket.opened_at
        predicted_reason = predict_reason(
            title=ticket.title,
            description=ticket.description,
            month=opened_at.month,
            hour=opened_at.hour,
            season=_season_from_month(opened_at.month),
            top_k=1,
        ).predicted_reason

        rows.append(
            {
                "ticket_id": ticket.id,
                "opened_at": opened_at.strftime("%Y-%m-%d %H:%M:%S"),
                "address_id": ticket.address_id,
                "uprava": uprava.name if uprava else "",
                "district": district.name,
                "street": street.name,
                "house_number": address.house_number,
                "title": ticket.title,
                "description": ticket.description or "",
                "reason_category": predicted_reason,
                "month": opened_at.month,
                "hour": opened_at.hour,
                "season": _season_from_month(opened_at.month),
            }
        )

    generated_df = pd.DataFrame(rows)

    sample_df = None
    for candidate in SAMPLE_DATASET_CANDIDATES:
        if candidate.exists():
            sample_df = pd.read_csv(candidate)
            break

    combined_df = pd.concat([sample_df, generated_df], ignore_index=True) if sample_df is not None else generated_df

    GENERATED_DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    combined_df.to_csv(GENERATED_DATASET_PATH, index=False, encoding="utf-8")
    return GENERATED_DATASET_PATH


def _season_from_month(month: int) -> str:
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


async def run_retraining_pipeline() -> None:
    from ml.address_model import train_address_model
    from ml.reason_forecast_model import train_reason_forecast_model
    from app.services.address_model import clear_address_model_cache
    from app.services.reason_forecast import clear_reason_forecast_cache

    state = load_ml_state()
    try:
        dataset_path = await _build_generated_dataset()
        address_result = train_address_model(dataset_path=dataset_path)
        reason_result = train_reason_forecast_model(dataset_path=dataset_path)
        clear_address_model_cache()
        clear_reason_forecast_cache()

        state["new_tickets_since_train"] = 0
        state["is_retraining"] = False
        state["last_trained_at"] = datetime.utcnow().isoformat()
        state["reason_forecast_model_version"] = int(state.get("reason_forecast_model_version", 0)) + 1
        state["address_model_version"] = int(state.get("address_model_version", 0)) + 1
        state["last_retrain_status"] = (
            f"ok: rows={address_result['rows']}, "
            f"unique_addresses={address_result['unique_addresses']}, "
            f"reason_labels={len(reason_result['labels'])}"
        )
    except Exception as exc:
        state["is_retraining"] = False
        state["last_retrain_status"] = f"failed: {exc}"
    save_ml_state(state)
