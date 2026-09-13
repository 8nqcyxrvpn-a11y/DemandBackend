import json
from pathlib import Path

from fastapi.testclient import TestClient

from server import app

client = TestClient(app)


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert set(response.json()) == {"status", "model_loaded", "collection_loaded"}


def test_collection_is_top_level_object():
    response = client.get("/collection")
    assert response.status_code == 200
    body = response.json()
    assert "collection" not in body
    assert len(body["products"]) == 5


def test_concept_drafts_preview_is_unevaluated_and_preserves_collection():
    collection_before = client.get("/collection").json()
    source_path = (
        Path(__file__).resolve().parent.parent
        / "data"
        / "experiments"
        / "concept_originator"
        / "first_hf_concept_drafts.json"
    )
    source_bytes_before = source_path.read_bytes()
    source_drafts = json.loads(source_bytes_before)["drafts"]

    response = client.get("/concept-drafts-preview")

    assert response.status_code == 200
    body = response.json()
    assert len(body["drafts"]) == 36
    assert body["drafts"] == source_drafts
    assert body["display_status"] == "Awaiting Independent Evaluation"
    assert body["evaluation_status"] == "pending"
    assert body["is_ai_generated"] is True
    assert body["is_temporary_preview"] is True

    forbidden_fields = {
        "evaluator_score",
        "evaluator_scores",
        "score",
        "scores",
        "ranking",
        "rank",
        "winner",
        "approval",
        "approved",
        "predicted_demand",
        "predicted_demand_units",
        "recommended_inventory",
        "recommended_inventory_units",
    }
    assert forbidden_fields.isdisjoint(body)
    for draft in body["drafts"]:
        assert forbidden_fields.isdisjoint(draft)

    assert source_path.read_bytes() == source_bytes_before
    assert client.get("/collection").json() == collection_before


def test_predict_demand():
    response = client.post(
        "/predict-demand",
        json={"price_usd": 4200, "trend_mentions": 780, "trend_growth_pct": 60, "inventory_units": 950},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "success"
    assert set(body["forecast"]) == {
        "predicted_demand_units", "safety_stock_units", "recommended_inventory_units"
    }
    assert all(isinstance(value, int) for value in body["forecast"].values())
    assert body["forecast"]["recommended_inventory_units"] >= body["forecast"]["predicted_demand_units"]


def test_invalid_demand_input_is_422():
    response = client.post("/predict-demand", json={"price_usd": "not-a-number"})
    assert response.status_code == 422


def test_extra_demand_input_is_422():
    response = client.post(
        "/predict-demand",
        json={
            "price_usd": 4200,
            "trend_mentions": 780,
            "trend_growth_pct": 60,
            "inventory_units": 950,
            "unsupported_feature": 1,
        },
    )
    assert response.status_code == 422


def test_trends_are_explicitly_synthetic():
    body = client.get("/trend-signals").json()
    assert body["is_live_data"] is False
    assert body["data_source"] == "synthetic_demo"
