"""Static precomputed collection access."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.model_loader import ArtifactError

REQUIRED_PRODUCT_FIELDS = {
    "category",
    "product",
    "predicted_demand_units",
    "recommended_inventory_units",
    "primary_trend",
    "trend_score",
    "concept_score",
    "image_prompt",
}


def _validate_collection(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ArtifactError("Collection artifact must contain a top-level object.")
    products = value.get("products")
    if not isinstance(products, list) or not products:
        raise ArtifactError("Collection artifact must contain a non-empty products list.")
    for position, product in enumerate(products, start=1):
        if not isinstance(product, dict):
            raise ArtifactError(f"Collection product {position} must be an object.")
        missing = REQUIRED_PRODUCT_FIELDS.difference(product)
        if missing:
            fields = ", ".join(sorted(missing))
            raise ArtifactError(f"Collection product {position} is missing: {fields}.")
        predicted = product["predicted_demand_units"]
        recommended = product["recommended_inventory_units"]
        if not isinstance(predicted, int) or isinstance(predicted, bool) or predicted < 0:
            raise ArtifactError(f"Collection product {position} has invalid predicted demand.")
        if not isinstance(recommended, int) or isinstance(recommended, bool) or recommended < predicted:
            raise ArtifactError(f"Collection product {position} has invalid recommended inventory.")
    return value


@lru_cache(maxsize=1)
def load_collection(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ArtifactError("Collection artifact is unavailable.")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactError("Collection artifact could not be loaded.") from exc
    return _validate_collection(value)
