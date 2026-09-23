"""Application configuration and artifact locations."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "demand_model.joblib"
COLLECTION_PATH = PROJECT_ROOT / "final_ai_collection.json"
DATASET_PATH = PROJECT_ROOT / "fashion_ai_starter_dataset.csv"


def cors_origins() -> list[str]:
    """Read comma-separated allowed origins, defaulting to prototype-friendly CORS."""
    value = os.getenv("CORS_ORIGINS", "*")
    return [origin.strip() for origin in value.split(",") if origin.strip()]


def google_trends_bigquery_project_id() -> str:
    value = os.getenv("GOOGLE_TRENDS_BIGQUERY_PROJECT_ID", "").strip()
    if not value:
        raise ValueError("GOOGLE_TRENDS_BIGQUERY_PROJECT_ID is required")
    return value


def google_trends_refresh_date() -> date:
    value = os.getenv("GOOGLE_TRENDS_REFRESH_DATE", "").strip()
    if not value:
        raise ValueError("GOOGLE_TRENDS_REFRESH_DATE is required")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("GOOGLE_TRENDS_REFRESH_DATE must use YYYY-MM-DD") from exc
