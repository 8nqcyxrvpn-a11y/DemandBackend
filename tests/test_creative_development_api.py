import json
import shutil
from dataclasses import fields
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.creative_development_service import (
    CreativeDevelopmentPaths,
    load_creative_development,
)
from app.model_loader import ArtifactError
from server import app


client = TestClient(app)
ROOT = Path(__file__).resolve().parent.parent
EXPECTED_SUFFIXES = {"021", "015", "023", "008", "025"}


def _historical_paths() -> list[Path]:
    configured = CreativeDevelopmentPaths()
    paths = [
        configured.drafts,
        configured.evaluation,
        configured.approval,
        configured.identity_proposals,
        configured.identity_decomposition,
        configured.refinement_v2,
    ]
    for run in (configured.base_visualization_run, configured.refinement_v2_visualization_run):
        paths.extend(
            [
                run / "manifest.json",
                run / "checkpoints/design-021-variation-1/lineage.json",
            ]
        )
    return paths


def test_creative_development_exact_persisted_mapping_and_flags():
    before = {path: path.read_bytes() for path in _historical_paths()}
    persisted = json.loads(CreativeDevelopmentPaths().refinement_v2.read_text())
    persisted_by_id = {item["concept_id"]: item for item in persisted["refinements"]}

    response = client.get("/creative-development")

    assert response.status_code == 200
    body = response.json()
    assert body["artifact_kind"] == "creative_development_read_only_projection"
    assert len(body["concepts"]) == 5
    assert {item["draft_id"].rsplit("-", 1)[-1] for item in body["concepts"]} == EXPECTED_SUFFIXES
    for concept in body["concepts"]:
        refinement = concept["creative_refinement_v2"]
        assert refinement == persisted_by_id[concept["draft_id"]]
        assert refinement["requires_re_evaluation"] is True
        assert refinement["evaluator_scores_transferred"] is False
        assert refinement["commercially_validated"] is False
        assert refinement["manufacturability_validated"] is False
        assert refinement["production_ready"] is False
        assert refinement["decorative_substitution"] is False
        assert refinement["unresolved_risks"] == persisted_by_id[concept["draft_id"]][
            "unresolved_risks"
        ]
        assert concept["identity_decomposition"]["concept_id"] == concept["draft_id"]
        assert concept["experimental_design_generation_approval"]["draft_id"] == concept[
            "draft_id"
        ]
    assert all(path.read_bytes() == content for path, content in before.items())


def test_creative_development_visualization_metadata_is_exact_and_geom_only():
    body = client.get("/creative-development").json()
    by_suffix = {item["draft_id"].rsplit("-", 1)[-1]: item for item in body["concepts"]}

    assert [item["visualizations"] for suffix, item in by_suffix.items() if suffix != "021"] == [
        [], [], [], []
    ]
    visualizations = by_suffix["021"]["visualizations"]
    assert [item["development_stage"] for item in visualizations] == [
        "base_approved_draft",
        "creative_refinement_v2",
    ]
    assert [item["output_asset_sha256"] for item in visualizations] == [
        "0ea05d4d081c47aadf72b3d60eb5dbac611480ad357d51c80d2c81137f3395e0",
        "ed579db4a037e604b5d63804d50a93ea64a04d4eabdfa7f69899fbfcca4fb98b",
    ]
    assert all(item["record_kind"] == "persisted_visualization_lineage_metadata" for item in visualizations)
    assert all(item["asset_publicly_available"] is False for item in visualizations)
    assert all(item["asset_file_verified_at_runtime"] is False for item in visualizations)
    assert all("image" not in item and "prompt" not in item for item in visualizations)


def test_creative_development_fails_closed_on_lineage_mismatch(tmp_path):
    source = CreativeDevelopmentPaths()
    copied = {}
    for descriptor in fields(source):
        original = getattr(source, descriptor.name)
        target = tmp_path / descriptor.name
        if original.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original / "manifest.json", target / "manifest.json")
            lineage = target / "checkpoints/design-021-variation-1/lineage.json"
            lineage.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(
                original / "checkpoints/design-021-variation-1/lineage.json", lineage
            )
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)
        copied[descriptor.name] = target
    refinement = json.loads(copied["refinement_v2"].read_text())
    refinement["source_approval_sha256"] = "0" * 64
    copied["refinement_v2"].write_text(json.dumps(refinement))
    paths = CreativeDevelopmentPaths(**copied)

    with pytest.raises(ArtifactError, match="lineage"):
        load_creative_development(paths)


def test_creative_development_does_not_require_png_assets(tmp_path):
    source = CreativeDevelopmentPaths()
    copied = {}
    for descriptor in fields(source):
        original = getattr(source, descriptor.name)
        target = tmp_path / descriptor.name
        if original.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original / "manifest.json", target / "manifest.json")
            lineage = target / "checkpoints/design-021-variation-1/lineage.json"
            lineage.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(
                original / "checkpoints/design-021-variation-1/lineage.json", lineage
            )
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)
        copied[descriptor.name] = target

    body = load_creative_development(CreativeDevelopmentPaths(**copied))

    assert len(body["concepts"]) == 5
    assert not list(tmp_path.rglob("*.png"))


def test_existing_public_api_routes_remain_available():
    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/collection").status_code == 200
    assert client.get("/concept-drafts-preview").status_code == 200
    assert client.get("/evaluated-concepts").status_code == 200
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
