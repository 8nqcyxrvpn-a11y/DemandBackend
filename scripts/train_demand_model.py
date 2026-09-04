#!/usr/bin/env python3
"""Train and evaluate the prototype RandomForest demand model."""

from __future__ import annotations

import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, r2_score
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DATASET = ROOT / "fashion_ai_starter_dataset.csv"
MODEL = ROOT / "demand_model.joblib"
FEATURES = ["price_usd", "trend_mentions", "trend_growth_pct", "inventory_units"]
TARGET = "sales_units"


def new_model() -> RandomForestRegressor:
    return RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=-1)


def report(label: str, actual: pd.Series, predicted) -> None:
    print(f"{label} MAE: {mean_absolute_error(actual, predicted):.2f}")
    print(f"{label} R²: {r2_score(actual, predicted):.3f}")
    print(f"{label} MAPE: {mean_absolute_percentage_error(actual, predicted) * 100:.2f}%")


def main() -> None:
    data = pd.read_csv(DATASET)
    data["date"] = pd.to_datetime(data["date"], errors="raise")
    data = data.sort_values("date").reset_index(drop=True)

    train_x, test_x, train_y, test_y = train_test_split(
        data[FEATURES], data[TARGET], test_size=0.2, random_state=42
    )
    random_model = new_model()
    random_model.fit(train_x, train_y)
    report("Random split", test_y, random_model.predict(test_x))

    split = int(len(data) * 0.8)
    future_model = new_model()
    future_model.fit(data.loc[: split - 1, FEATURES], data.loc[: split - 1, TARGET])
    report("Time split", data.loc[split:, TARGET], future_model.predict(data.loc[split:, FEATURES]))
    print(f"Time split rows: {split} train, {len(data) - split} future test")

    final_model = new_model()
    final_model.fit(data[FEATURES], data[TARGET])
    joblib.dump(final_model, MODEL)
    print(f"Saved {MODEL.name}")


if __name__ == "__main__":
    main()

