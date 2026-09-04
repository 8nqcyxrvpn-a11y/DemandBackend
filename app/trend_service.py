"""Transparent trend ranking over the bundled synthetic demo data."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

REQUIRED_COLUMNS = {"date", "color", "trend_mentions", "trend_growth_pct"}


def build_trend_signals(dataset_path: Path) -> list[dict[str, Any]]:
    data = pd.read_csv(dataset_path)
    missing = REQUIRED_COLUMNS.difference(data.columns)
    if missing:
        raise ValueError(f"Dataset is missing required columns: {', '.join(sorted(missing))}")
    if data.empty:
        raise ValueError("Dataset does not contain any trend observations")
    data["date"] = pd.to_datetime(data["date"], errors="raise")
    for column in ("trend_mentions", "trend_growth_pct"):
        data[column] = pd.to_numeric(data[column], errors="raise")
        if not data[column].map(lambda value: pd.notna(value) and abs(value) != float("inf")).all():
            raise ValueError(f"Dataset column {column} contains non-finite values")
    if data["color"].isna().any() or (data["color"].astype(str).str.strip() == "").any():
        raise ValueError("Dataset contains a missing color signal")
    grouped = data.groupby("color", as_index=False).agg(
        avg_mentions=("trend_mentions", "mean"),
        avg_growth_pct=("trend_growth_pct", "mean"),
        observations=("color", "size"),
    )
    grouped["trend_score"] = (
        grouped["avg_mentions"].rank(pct=True) * 50
        + grouped["avg_growth_pct"].rank(pct=True) * 50
    )
    grouped = grouped.sort_values(["trend_score", "color"], ascending=[False, True])
    signals = []
    for row in grouped.itertuples(index=False):
        signals.append({
            "signal": row.color,
            "signal_type": "color",
            "avg_mentions": round(float(row.avg_mentions), 2),
            "avg_growth_pct": round(float(row.avg_growth_pct), 2),
            "observations": int(row.observations),
            "trend_score": round(float(row.trend_score), 2),
        })
    return signals
