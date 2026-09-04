import json

import pandas as pd
import pytest

from app.collection_service import load_collection
from app.model_loader import ArtifactError
from app.trend_service import build_trend_signals


def test_collection_rejects_incomplete_product(tmp_path):
    path = tmp_path / "collection.json"
    path.write_text(json.dumps({"products": [{"product": "Incomplete"}]}), encoding="utf-8")

    with pytest.raises(ArtifactError, match="missing"):
        load_collection(path)


def test_trends_reject_empty_dataset(tmp_path):
    path = tmp_path / "trends.csv"
    pd.DataFrame(columns=["date", "color", "trend_mentions", "trend_growth_pct"]).to_csv(
        path, index=False
    )

    with pytest.raises(ValueError, match="does not contain"):
        build_trend_signals(path)
