#!/usr/bin/env python3
"""Validate all runtime artifacts before deployment."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.collection_service import load_collection
from app.config import COLLECTION_PATH, DATASET_PATH, MODEL_PATH
from app.model_loader import load_model
from app.trend_service import build_trend_signals


def main() -> None:
    model = load_model(MODEL_PATH)
    collection = load_collection(COLLECTION_PATH)
    trends = build_trend_signals(DATASET_PATH)
    assert model.__class__.__name__ == "RandomForestRegressor"
    assert isinstance(collection.get("products"), list)
    assert len(trends) > 0
    print("Artifacts valid: model, collection, and synthetic trend dataset")


if __name__ == "__main__":
    main()

