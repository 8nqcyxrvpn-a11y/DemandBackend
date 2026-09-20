"""Fail-closed access to two persisted experimental design visualizations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from app.creative_development_service import (
    DEFAULT_PATHS,
    CreativeDevelopmentPaths,
    load_creative_development,
)
from app.model_loader import ArtifactError


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
BASE_ASSET_SHA256 = "0ea05d4d081c47aadf72b3d60eb5dbac611480ad357d51c80d2c81137f3395e0"
REFINEMENT_V2_ASSET_SHA256 = (
    "ed579db4a037e604b5d63804d50a93ea64a04d4eabdfa7f69899fbfcca4fb98b"
)


class VisualizationNotFoundError(LookupError):
    """The identifier is well formed but is not in the fixed asset registry."""


@dataclass(frozen=True)
class DesignVisualizationAsset:
    content: bytes
    sha256: str


@dataclass(frozen=True)
class _RegistryEntry:
    development_stage: str
    run_field: str
    unit_key: str = "design-021-variation-1"


_ASSET_REGISTRY = {
    BASE_ASSET_SHA256: _RegistryEntry(
        development_stage="base_approved_draft",
        run_field="base_visualization_run",
    ),
    REFINEMENT_V2_ASSET_SHA256: _RegistryEntry(
        development_stage="creative_refinement_v2",
        run_field="refinement_v2_visualization_run",
    ),
}


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_lineage(path: Path) -> tuple[dict, bytes]:
    if not path.is_file() or path.is_symlink():
        raise ArtifactError("Design visualization lineage is unavailable.")
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactError("Design visualization lineage could not be loaded.") from exc
    if not isinstance(value, dict):
        raise ArtifactError("Design visualization lineage must be an object.")
    return value, raw


def load_design_visualization(
    asset_sha256: str,
    paths: CreativeDevelopmentPaths = DEFAULT_PATHS,
) -> DesignVisualizationAsset:
    """Validate complete provenance and return bytes for one allowlisted PNG."""
    entry = _ASSET_REGISTRY.get(asset_sha256)
    if entry is None:
        raise VisualizationNotFoundError("Design visualization is not available.")

    development = load_creative_development(paths)
    concepts = development.get("concepts", [])
    geom = [item for item in concepts if item.get("product_name") == "Geom Grid Monk"]
    if len(geom) != 1:
        raise ArtifactError("Design visualization concept provenance is inconsistent.")
    matches = [
        item
        for item in geom[0].get("visualizations", [])
        if item.get("development_stage") == entry.development_stage
        and item.get("output_asset_sha256") == asset_sha256
        and item.get("unit_key") == entry.unit_key
    ]
    if len(matches) != 1:
        raise ArtifactError("Design visualization metadata provenance is inconsistent.")
    metadata = matches[0]

    run_path = getattr(paths, entry.run_field)
    checkpoint = run_path / "checkpoints" / entry.unit_key
    lineage, lineage_raw = _read_lineage(checkpoint / "lineage.json")
    if (
        _sha256(lineage_raw) != metadata.get("lineage_sha256")
        or lineage.get("unit_key") != entry.unit_key
        or lineage.get("draft_id") != geom[0].get("draft_id")
        or lineage.get("output_asset_filename") != "design.png"
        or lineage.get("output_asset_sha256") != asset_sha256
        or lineage.get("generation_provider") != metadata.get("generation_provider")
        or lineage.get("generation_model") != metadata.get("generation_model")
        or lineage.get("generation_timestamp") != metadata.get("generation_timestamp")
        or lineage.get("variation_number") != metadata.get("variation_number")
        or lineage.get("variation_name") != metadata.get("variation_name")
    ):
        raise ArtifactError("Design visualization lineage is inconsistent.")

    asset_path = checkpoint / "design.png"
    if not asset_path.is_file() or asset_path.is_symlink():
        raise ArtifactError("Design visualization asset is unavailable.")
    try:
        content = asset_path.read_bytes()
    except OSError as exc:
        raise ArtifactError("Design visualization asset could not be loaded.") from exc
    if not content.startswith(PNG_SIGNATURE) or _sha256(content) != asset_sha256:
        raise ArtifactError("Design visualization asset integrity validation failed.")
    return DesignVisualizationAsset(content=content, sha256=asset_sha256)
