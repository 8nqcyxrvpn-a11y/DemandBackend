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


def test_evaluated_concepts_maps_exact_v21_artifacts_read_only():
    root = Path(__file__).resolve().parent.parent
    draft_path = root / "data/experiments/concept_originator/first_hf_concept_drafts.json"
    evaluation_path = root / (
        "data/experiments/concept_originator/evaluations/"
        "evaluation_20260917_gpt_oss_pair_two_sided_v21/evaluation.json"
    )
    approval_path = root / (
        "data/experiments/concept_originator/design_generation_approvals/"
        "evaluation_20260917_gpt_oss_pair_two_sided_v21_initial_five.json"
    )
    protected_bytes = {
        path: path.read_bytes() for path in (draft_path, evaluation_path, approval_path)
    }
    drafts = json.loads(protected_bytes[draft_path])["drafts"]
    evaluation = json.loads(protected_bytes[evaluation_path])
    approval = json.loads(protected_bytes[approval_path])

    response = client.get("/evaluated-concepts")

    assert response.status_code == 200
    body = response.json()
    assert body["artifact_kind"] == "evaluated_concepts_read_only_projection"
    assert body["experimental"] is True
    assert body["is_synthetic_input"] is True
    assert body["evaluation_provenance"]["run_id"].endswith("v21")
    assert body["evaluation_provenance"]["evaluator"] == evaluation["report"]["evaluator"]
    assert body["evaluator_selection"] == evaluation["selection"]
    assert len(body["concepts"]) == 36

    approval_by_id = {item["draft_id"]: item for item in approval["approvals"]}
    decisions = {item["draft_id"]: item for item in evaluation["decisions"]}
    for index, concept in enumerate(body["concepts"]):
        assessment = evaluation["report"]["assessments"][index]
        decision = decisions[assessment["draft_id"]]
        assert concept["draft_id"] == assessment["draft_id"]
        assert concept["product_name"] == drafts[index]["product_name"]
        assert concept["category"] == drafts[index]["category"]
        assert concept["evaluation_status"] == decision["disposition"]
        assert concept["structural_evaluation"] == assessment["structural"]
        assert concept["contextual_evaluation"] == assessment["contextual"]
        assert concept["evaluation_decision"] == decision
        assert concept["evaluator_selected"] is False
        assert concept["approved_for_experimental_design_generation"] == (
            concept["draft_id"] in approval_by_id
        )
        assert concept["experimental_design_generation_approval"] == approval_by_id.get(
            concept["draft_id"]
        )
        assert concept["rejection_reasons"] == (
            decision["reasons"] if decision["disposition"] == "reject" else []
        )

    assert sum(
        item["approved_for_experimental_design_generation"] for item in body["concepts"]
    ) == 5
    assert all(path.read_bytes() == before for path, before in protected_bytes.items())


def test_existing_public_routes_still_work_with_evaluated_concepts_route():
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/collection").status_code == 200
    assert client.get("/concept-drafts-preview").status_code == 200
    assert client.get("/trend-signals").status_code == 200
    assert client.get("/model-info").status_code == 200
    assert client.post(
        "/predict-demand",
        json={
            "price_usd": 4200,
            "trend_mentions": 780,
            "trend_growth_pct": 60,
            "inventory_units": 950,
        },
    ).status_code == 200


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
