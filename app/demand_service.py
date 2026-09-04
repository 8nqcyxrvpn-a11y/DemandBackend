"""Dynamic demand inference and inventory recommendation."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

from app.schemas import DemandInput
from app.utils import deterministic_units

FEATURE_NAMES = ["price_usd", "trend_mentions", "trend_growth_pct", "inventory_units"]


def predict_demand(payload: DemandInput, model: Any) -> dict[str, Any]:
    row = pd.DataFrame(
        [[payload.price_usd, payload.trend_mentions, payload.trend_growth_pct, payload.inventory_units]],
        columns=FEATURE_NAMES,
    )
    predicted = deterministic_units(model.predict(row)[0])
    safety_stock = math.ceil(predicted * 0.15)
    return {
        "status": "success",
        "model": "RandomForestRegressor",
        "prediction_type": "dynamic",
        "inputs": payload.model_dump(),
        "forecast": {
            "predicted_demand_units": predicted,
            "safety_stock_units": safety_stock,
            "recommended_inventory_units": predicted + safety_stock,
        },
    }
