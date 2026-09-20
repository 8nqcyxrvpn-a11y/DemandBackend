"""Fail-closed access to allowlisted persisted experimental design visualizations."""

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
INTERLINKED_RING_PURSE_ASSET_SHA256 = (
    "b038b4537d7d7d230f84c60b71b57b77c513e3f280a3ad603d80f7d8283341b5"
)
AMBIENT_CUFF_BLAZER_ASSET_SHA256 = (
    "bc9929efb9098b67631faf7a5420cfe5ecf754ec957b10705dfe884a9671cb58"
)
HOLLOW_COLUMN_BRIEF_ASSET_SHA256 = (
    "c7bd36beff54df1070ff012586cd3574fdaec68ab38081c7a7ce08072ab2d9e7"
)
KINETIC_BIAS_SKIRT_ASSET_SHA256 = (
    "67407238d761d8bf89319b29e27c59d217b1dc240eae83791204829abdb85163"
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
    draft_id: str
    unit_key: str = "design-021-variation-1"


_ASSET_REGISTRY = {
    BASE_ASSET_SHA256: _RegistryEntry(
        development_stage="base_approved_draft",
        run_field="base_visualization_run",
        draft_id="draft-62985a9b7ad80e4844d1bc1918bcbba8ef064d500f13ef395c2854fa793af64b-021",
    ),
    REFINEMENT_V2_ASSET_SHA256: _RegistryEntry(
        development_stage="creative_refinement_v2",
        run_field="refinement_v2_visualization_run",
        draft_id="draft-62985a9b7ad80e4844d1bc1918bcbba8ef064d500f13ef395c2854fa793af64b-021",
    ),
    INTERLINKED_RING_PURSE_ASSET_SHA256: _RegistryEntry(
        development_stage="creative_refinement_v2",
        run_field="interlinked_ring_purse_visualization_run",
        draft_id="draft-62985a9b7ad80e4844d1bc1918bcbba8ef064d500f13ef395c2854fa793af64b-015",
        unit_key="design-015-variation-1",
    ),
    AMBIENT_CUFF_BLAZER_ASSET_SHA256: _RegistryEntry(
        development_stage="creative_refinement_v2",
        run_field="ambient_cuff_blazer_visualization_run",
        draft_id="draft-62985a9b7ad80e4844d1bc1918bcbba8ef064d500f13ef395c2854fa793af64b-023",
        unit_key="design-023-variation-1",
    ),
    HOLLOW_COLUMN_BRIEF_ASSET_SHA256: _RegistryEntry(
        development_stage="creative_refinement_v2",
        run_field="hollow_column_brief_visualization_run",
        draft_id="draft-62985a9b7ad80e4844d1bc1918bcbba8ef064d500f13ef395c2854fa793af64b-008",
        unit_key="design-008-variation-1",
    ),
    KINETIC_BIAS_SKIRT_ASSET_SHA256: _RegistryEntry(
        development_stage="creative_refinement_v2",
        run_field="kinetic_bias_skirt_visualization_run",
        draft_id="draft-62985a9b7ad80e4844d1bc1918bcbba8ef064d500f13ef395c2854fa793af64b-025",
        unit_key="design-025-variation-1",
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
    matched_concepts = [item for item in concepts if item.get("draft_id") == entry.draft_id]
    if len(matched_concepts) != 1:
        raise ArtifactError("Design visualization concept provenance is inconsistent.")
    concept = matched_concepts[0]
    matches = [
        item
        for item in concept.get("visualizations", [])
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
        or lineage.get("draft_id") != entry.draft_id
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
