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
RUN_UNITS = {
    "base_visualization_run": "design-021-variation-1",
    "refinement_v2_visualization_run": "design-021-variation-1",
    "interlinked_ring_purse_visualization_run": "design-015-variation-1",
    "ambient_cuff_blazer_visualization_run": "design-023-variation-1",
    "hollow_column_brief_visualization_run": "design-008-variation-1",
    "kinetic_bias_skirt_visualization_run": "design-025-variation-1",
}


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
    for field, unit in RUN_UNITS.items():
        run = getattr(configured, field)
        paths.extend(
            [
                run / "manifest.json",
                run / "checkpoints" / unit / "lineage.json",
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


def test_creative_development_visualization_metadata_is_exact_for_all_five():
    body = client.get("/creative-development").json()
    by_suffix = {item["draft_id"].rsplit("-", 1)[-1]: item for item in body["concepts"]}

    geom_visualizations = by_suffix["021"]["visualizations"]
    assert [item["development_stage"] for item in geom_visualizations] == [
        "base_approved_draft",
        "creative_refinement_v2",
    ]
    assert [item["output_asset_sha256"] for item in geom_visualizations] == [
        "0ea05d4d081c47aadf72b3d60eb5dbac611480ad357d51c80d2c81137f3395e0",
        "ed579db4a037e604b5d63804d50a93ea64a04d4eabdfa7f69899fbfcca4fb98b",
    ]
    expected = {
        "015": (
            "experimental_design_generation_015_refinement_v2_architectural_clarity",
            "design-015-variation-1",
            "b038b4537d7d7d230f84c60b71b57b77c513e3f280a3ad603d80f7d8283341b5",
            "6b88ac1c33334dd1de91f7bcf016cd8182bb186a1bfb5d314c2f59bbbf364751",
        ),
        "023": (
            "experimental_design_generation_023_refinement_v2_architectural_clarity",
            "design-023-variation-1",
            "bc9929efb9098b67631faf7a5420cfe5ecf754ec957b10705dfe884a9671cb58",
            "d4802201362dedfac4d1d237623ce7c8803aa19fe54b993f13dff6d034a04fe0",
        ),
        "008": (
            "experimental_design_generation_008_refinement_v2_architectural_clarity",
            "design-008-variation-1",
            "c7bd36beff54df1070ff012586cd3574fdaec68ab38081c7a7ce08072ab2d9e7",
            "56e40aabc1e99132208f94100e5182afb46bcd5654ea7026078aa38d55fa8718",
        ),
        "025": (
            "experimental_design_generation_025_refinement_v2_architectural_clarity",
            "design-025-variation-1",
            "67407238d761d8bf89319b29e27c59d217b1dc240eae83791204829abdb85163",
            "60e850834b96315ee37efecf89db67b4b9acab12a66568f8eb652d55cfc15e91",
        ),
    }
    for suffix, (run_id, unit_key, output_sha256, refinement_sha256) in expected.items():
        visualizations = by_suffix[suffix]["visualizations"]
        assert len(visualizations) == 1
        visualization = visualizations[0]
        assert visualization["development_stage"] == "creative_refinement_v2"
        assert visualization["run_id"] == run_id
        assert visualization["unit_key"] == unit_key
        assert visualization["variation_number"] == 1
        assert visualization["variation_name"] == "architectural_clarity"
        assert visualization["output_asset_sha256"] == output_sha256
        assert visualization["refinement_v2_sha256"] == refinement_sha256
        assert visualization["refinement_v2_artifact_sha256"] == body["provenance"][
            "creative_refinement_v2_sha256"
        ]
    visualizations = [
        visualization
        for concept in body["concepts"]
        for visualization in concept["visualizations"]
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
            unit = RUN_UNITS[descriptor.name]
            lineage = target / "checkpoints" / unit / "lineage.json"
            lineage.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(
                original / "checkpoints" / unit / "lineage.json", lineage
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
            unit = RUN_UNITS[descriptor.name]
            lineage = target / "checkpoints" / unit / "lineage.json"
            lineage.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(
                original / "checkpoints" / unit / "lineage.json", lineage
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
