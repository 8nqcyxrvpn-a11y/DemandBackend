"""Read-only access to unevaluated AI-generated concept drafts."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.model_loader import ArtifactError


CONCEPT_DRAFTS_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "experiments"
    / "concept_originator"
    / "first_hf_concept_drafts.json"
)

REQUIRED_DRAFT_FIELDS = {
    "product_name",
    "category",
    "core_structural_idea",
    "silhouette_form",
    "construction_mechanism",
    "materials_and_behavior",
    "colors",
    "product_behavior",
    "whitespace_rationale",
    "trend_signal_ids",
    "brand_evidence_ids",
    "manufacturability_explanation",
    "image_prompt",
    "uncertainty_limitations",
}
LIST_DRAFT_FIELDS = {
    "materials_and_behavior",
    "colors",
    "trend_signal_ids",
    "brand_evidence_ids",
    "uncertainty_limitations",
}


def _validate_preview_artifact(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        raise ArtifactError("Concept draft preview artifact must be an object.")
    if value.get("artifact_kind") != "ai_generated_concept_drafts_experimental":
        raise ArtifactError("Concept draft preview artifact has an invalid kind.")
    if value.get("experimental") is not True or value.get("eligible_for_public_api") is not False:
        raise ArtifactError("Concept draft preview artifact has invalid preview eligibility metadata.")

    drafts = value.get("drafts")
    if not isinstance(drafts, list) or len(drafts) != 36:
        raise ArtifactError("Concept draft preview artifact must contain exactly 36 drafts.")

    for draft in drafts:
        if not isinstance(draft, dict) or set(draft) != REQUIRED_DRAFT_FIELDS:
            raise ArtifactError("Concept draft preview artifact contains an invalid draft shape.")
        for field, field_value in draft.items():
            if field in LIST_DRAFT_FIELDS:
                if (
                    not isinstance(field_value, list)
                    or not field_value
                    or any(not isinstance(item, str) or not item.strip() for item in field_value)
                ):
                    raise ArtifactError("Concept draft preview artifact contains an invalid draft list.")
            elif not isinstance(field_value, str) or not field_value.strip():
                raise ArtifactError("Concept draft preview artifact contains an invalid draft value.")
    return drafts


@lru_cache(maxsize=1)
def load_concept_drafts_preview(path: Path = CONCEPT_DRAFTS_PATH) -> dict[str, Any]:
    """Validate and expose the immutable draft artifact as an unevaluated preview."""
    if not path.is_file():
        raise ArtifactError("Concept draft preview artifact is unavailable.")

    try:
        raw_artifact = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactError("Concept draft preview artifact could not be loaded.") from exc

    drafts = _validate_preview_artifact(raw_artifact)

    return {
        "display_status": "Awaiting Independent Evaluation",
        "evaluation_status": "pending",
        "is_ai_generated": True,
        "is_temporary_preview": True,
        "drafts": drafts,
    }
