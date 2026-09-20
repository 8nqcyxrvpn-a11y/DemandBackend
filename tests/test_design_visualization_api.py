import hashlib
import json
import shutil
from dataclasses import fields
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.creative_development_service import CreativeDevelopmentPaths
from app.design_visualization_service import (
    AMBIENT_CUFF_BLAZER_ASSET_SHA256,
    BASE_ASSET_SHA256,
    HOLLOW_COLUMN_BRIEF_ASSET_SHA256,
    INTERLINKED_RING_PURSE_ASSET_SHA256,
    KINETIC_BIAS_SKIRT_ASSET_SHA256,
    REFINEMENT_V2_ASSET_SHA256,
    load_design_visualization,
)
from app.model_loader import ArtifactError
from server import app


client = TestClient(app)
ASSETS = {
    BASE_ASSET_SHA256: (
        CreativeDevelopmentPaths().base_visualization_run
        / "checkpoints/design-021-variation-1/design.png"
    ),
    REFINEMENT_V2_ASSET_SHA256: (
        CreativeDevelopmentPaths().refinement_v2_visualization_run
        / "checkpoints/design-021-variation-1/design.png"
    ),
    INTERLINKED_RING_PURSE_ASSET_SHA256: (
        CreativeDevelopmentPaths().interlinked_ring_purse_visualization_run
        / "checkpoints/design-015-variation-1/design.png"
    ),
    AMBIENT_CUFF_BLAZER_ASSET_SHA256: (
        CreativeDevelopmentPaths().ambient_cuff_blazer_visualization_run
        / "checkpoints/design-023-variation-1/design.png"
    ),
    HOLLOW_COLUMN_BRIEF_ASSET_SHA256: (
        CreativeDevelopmentPaths().hollow_column_brief_visualization_run
        / "checkpoints/design-008-variation-1/design.png"
    ),
    KINETIC_BIAS_SKIRT_ASSET_SHA256: (
        CreativeDevelopmentPaths().kinetic_bias_skirt_visualization_run
        / "checkpoints/design-025-variation-1/design.png"
    ),
}
RUN_UNITS = {
    "base_visualization_run": "design-021-variation-1",
    "refinement_v2_visualization_run": "design-021-variation-1",
    "interlinked_ring_purse_visualization_run": "design-015-variation-1",
    "ambient_cuff_blazer_visualization_run": "design-023-variation-1",
    "hollow_column_brief_visualization_run": "design-008-variation-1",
    "kinetic_bias_skirt_visualization_run": "design-025-variation-1",
}


@pytest.mark.parametrize("asset_sha256", list(ASSETS))
def test_exact_visualization_returns_verified_png_and_headers(asset_sha256):
    expected = ASSETS[asset_sha256].read_bytes()

    response = client.get(f"/design-visualizations/{asset_sha256}")

    assert response.status_code == 200
    assert response.content == expected
    assert hashlib.sha256(response.content).hexdigest() == asset_sha256
    assert response.headers["content-type"] == "image/png"
    assert response.headers["etag"] == f'"{asset_sha256}"'
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.headers["x-content-sha256"] == asset_sha256


def test_unknown_valid_visualization_identifier_is_404():
    response = client.get(f"/design-visualizations/{'a' * 64}")
    assert response.status_code == 404


@pytest.mark.parametrize("identifier", ["short", "A" * 64, "g" * 64, "0" * 65])
def test_malformed_visualization_identifier_is_422(identifier):
    assert client.get(f"/design-visualizations/{identifier}").status_code == 422


def _copy_runtime(tmp_path: Path, *, include_assets: bool = True) -> CreativeDevelopmentPaths:
    source = CreativeDevelopmentPaths()
    copied = {}
    for descriptor in fields(source):
        original = getattr(source, descriptor.name)
        target = tmp_path / descriptor.name
        if original.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original / "manifest.json", target / "manifest.json")
            unit_key = RUN_UNITS[descriptor.name]
            unit = target / "checkpoints" / unit_key
            unit.mkdir(parents=True, exist_ok=True)
            shutil.copy2(
                original / "checkpoints" / unit_key / "lineage.json",
                unit / "lineage.json",
            )
            if include_assets:
                shutil.copy2(
                    original / "checkpoints" / unit_key / "design.png",
                    unit / "design.png",
                )
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(original, target)
        copied[descriptor.name] = target
    return CreativeDevelopmentPaths(**copied)


def test_missing_known_asset_fails_closed(tmp_path):
    paths = _copy_runtime(tmp_path, include_assets=False)
    with pytest.raises(ArtifactError, match="unavailable"):
        load_design_visualization(BASE_ASSET_SHA256, paths)


def test_corrupted_known_asset_fails_closed(tmp_path):
    paths = _copy_runtime(tmp_path)
    asset = (
        paths.base_visualization_run
        / "checkpoints/design-021-variation-1/design.png"
    )
    asset.write_bytes(b"not a png")
    with pytest.raises(ArtifactError, match="integrity"):
        load_design_visualization(BASE_ASSET_SHA256, paths)


def test_provenance_mismatch_fails_closed(tmp_path):
    paths = _copy_runtime(tmp_path)
    lineage_path = (
        paths.base_visualization_run
        / "checkpoints/design-021-variation-1/lineage.json"
    )
    lineage = json.loads(lineage_path.read_text())
    lineage["source_evaluation_sha256"] = "0" * 64
    lineage_path.write_text(json.dumps(lineage))
    with pytest.raises(ArtifactError, match="lineage"):
        load_design_visualization(BASE_ASSET_SHA256, paths)


def test_symlink_asset_fails_closed(tmp_path):
    paths = _copy_runtime(tmp_path, include_assets=False)
    external = tmp_path / "external.png"
    external.write_bytes(ASSETS[BASE_ASSET_SHA256].read_bytes())
    asset = (
        paths.base_visualization_run
        / "checkpoints/design-021-variation-1/design.png"
    )
    asset.symlink_to(external)
    with pytest.raises(ArtifactError, match="unavailable"):
        load_design_visualization(BASE_ASSET_SHA256, paths)


def test_visualization_route_preserves_historical_files_and_public_routes():
    paths = CreativeDevelopmentPaths()
    historical = [
        paths.drafts,
        paths.evaluation,
        paths.approval,
        paths.identity_proposals,
        paths.identity_decomposition,
        paths.refinement_v2,
        paths.base_visualization_run / "manifest.json",
        paths.base_visualization_run / "checkpoints/design-021-variation-1/lineage.json",
        ASSETS[BASE_ASSET_SHA256],
        paths.refinement_v2_visualization_run / "manifest.json",
        paths.refinement_v2_visualization_run / "checkpoints/design-021-variation-1/lineage.json",
        ASSETS[REFINEMENT_V2_ASSET_SHA256],
    ]
    for field, unit in RUN_UNITS.items():
        if field in {"base_visualization_run", "refinement_v2_visualization_run"}:
            continue
        run = getattr(paths, field)
        historical.extend([
            run / "manifest.json",
            run / "checkpoints" / unit / "lineage.json",
        ])
    historical.extend(ASSETS[asset_sha256] for asset_sha256 in (
        INTERLINKED_RING_PURSE_ASSET_SHA256,
        AMBIENT_CUFF_BLAZER_ASSET_SHA256,
        HOLLOW_COLUMN_BRIEF_ASSET_SHA256,
        KINETIC_BIAS_SKIRT_ASSET_SHA256,
    ))
    before = {path: path.read_bytes() for path in historical}

    assert client.get("/").status_code == 200
    assert client.get("/health").status_code == 200
    assert client.get("/collection").status_code == 200
    assert client.get("/concept-drafts-preview").status_code == 200
    assert client.get("/evaluated-concepts").status_code == 200
    assert client.get("/creative-development").status_code == 200
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
    assert all(path.read_bytes() == content for path, content in before.items())
