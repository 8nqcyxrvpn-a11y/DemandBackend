"""Application configuration and artifact locations."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "demand_model.joblib"
COLLECTION_PATH = PROJECT_ROOT / "final_ai_collection.json"
DATASET_PATH = PROJECT_ROOT / "fashion_ai_starter_dataset.csv"


def cors_origins() -> list[str]:
    """Read comma-separated allowed origins, defaulting to prototype-friendly CORS."""
    value = os.getenv("CORS_ORIGINS", "*")
    return [origin.strip() for origin in value.split(",") if origin.strip()]

