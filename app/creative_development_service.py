"""Read-only projection of the five persisted creative-refinement v2 records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.model_loader import ArtifactError


ROOT = Path(__file__).resolve().parent.parent
EXPERIMENT_ROOT = ROOT / "data" / "experiments" / "concept_originator"
EVALUATION_RUN_ID = "evaluation_20260917_gpt_oss_pair_two_sided_v21"


@dataclass(frozen=True)
class CreativeDevelopmentPaths:
    drafts: Path = EXPERIMENT_ROOT / "first_hf_concept_drafts.json"
    evaluation: Path = (
        EXPERIMENT_ROOT / "evaluations" / EVALUATION_RUN_ID / "evaluation.json"
    )
    approval: Path = (
        EXPERIMENT_ROOT
        / "design_generation_approvals"
        / f"{EVALUATION_RUN_ID}_initial_five.json"
    )
    identity_proposals: Path = (
        EXPERIMENT_ROOT
        / "concept_identity_inputs"
        / "v21_approved_five_identity_proposals.json"
    )
    identity_decomposition: Path = (
        EXPERIMENT_ROOT
        / "concept_identity_decompositions"
        / f"{EVALUATION_RUN_ID}_identity_decomposition_v1.json"
    )
    refinement_v2: Path = (
        EXPERIMENT_ROOT
        / "creative_refinements"
        / f"{EVALUATION_RUN_ID}_creative_refinement_v2.json"
    )
    base_visualization_run: Path = (
        EXPERIMENT_ROOT
        / "design_generations"
        / "experimental_design_generation_20260918_v21_initial_five_hf_krea2_turbo"
    )
    refinement_v2_visualization_run: Path = (
        EXPERIMENT_ROOT
        / "design_generations"
        / "experimental_design_generation_20260919_geom_grid_monk_refinement_v2_audit"
    )
    interlinked_ring_purse_visualization_run: Path = (
        EXPERIMENT_ROOT
        / "design_generations"
        / "experimental_design_generation_015_refinement_v2_architectural_clarity"
    )
    ambient_cuff_blazer_visualization_run: Path = (
        EXPERIMENT_ROOT
        / "design_generations"
        / "experimental_design_generation_023_refinement_v2_architectural_clarity"
    )
    hollow_column_brief_visualization_run: Path = (
        EXPERIMENT_ROOT
        / "design_generations"
        / "experimental_design_generation_008_refinement_v2_architectural_clarity"
    )
    kinetic_bias_skirt_visualization_run: Path = (
        EXPERIMENT_ROOT
        / "design_generations"
        / "experimental_design_generation_025_refinement_v2_architectural_clarity"
    )


DEFAULT_PATHS = CreativeDevelopmentPaths()
FALSE_VALIDATION_FIELDS = (
    "evaluator_scores_transferred",
    "commercially_validated",
    "manufacturability_validated",
    "production_ready",
    "decorative_substitution",
)


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _canonical(value: Any, *, newline: bool = False) -> bytes:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return (encoded + ("\n" if newline else "")).encode()


def _read_json(path: Path, label: str) -> tuple[dict[str, Any], bytes, str]:
    if not path.is_file():
        raise ArtifactError(f"{label} artifact is unavailable.")
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"{label} artifact could not be loaded.") from exc
    if not isinstance(value, dict):
        raise ArtifactError(f"{label} artifact must be an object.")
    return value, raw, _sha256(raw)


def _resolve_pointer(source: Any, pointer: str) -> Any:
    if not isinstance(pointer, str) or not pointer.startswith("/"):
        raise ArtifactError("Identity decomposition contains an invalid source pointer.")
    value = source
    try:
        for raw_token in pointer[1:].split("/"):
            token = raw_token.replace("~1", "/").replace("~0", "~")
            value = value[int(token)] if isinstance(value, list) else value[token]
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise ArtifactError("Identity decomposition source pointer could not be resolved.") from exc
    return value


def _validate_visualization(
    *,
    run_path: Path,
    stage: str,
    hashes: dict[str, str],
    approved_ids: set[str],
    approval_by_id: dict[str, dict[str, Any]],
    decomposition_by_id: dict[str, dict[str, Any]],
    refinement_by_id: dict[str, dict[str, Any]],
    planned_ids: set[str],
    checkpoint_unit_key: str,
) -> tuple[str, dict[str, Any]]:
    manifest, _, manifest_sha256 = _read_json(run_path / "manifest.json", "Visualization manifest")
    plan = manifest.get("plan")
    if not isinstance(plan, dict) or manifest.get("plan_sha256") != _sha256(
        _canonical(plan, newline=True)
    ):
        raise ArtifactError("Visualization manifest plan hash is inconsistent.")
    if (
        plan.get("artifact_kind") != "private_experimental_design_generation_plan"
        or plan.get("private") is not True
        or plan.get("purpose") != "experimental_design_generation"
        or plan.get("approval_artifact_sha256") != hashes["approval"]
        or plan.get("source_evaluation_sha256") != hashes["evaluation"]
        or plan.get("source_drafts_artifact_sha256") != hashes["drafts"]
    ):
        raise ArtifactError("Visualization manifest source lineage is inconsistent.")
    if stage == "creative_refinement_v2":
        if (
            plan.get("identity_decomposition_artifact_sha256") != hashes["identity_decomposition"]
            or plan.get("refinement_v2_artifact_sha256") != hashes["refinement_v2"]
        ):
            raise ArtifactError("Refinement-v2 visualization lineage is inconsistent.")
    elif plan.get("identity_decomposition_artifact_sha256") is not None or plan.get(
        "refinement_v2_artifact_sha256"
    ) is not None:
        raise ArtifactError("Base visualization unexpectedly references creative refinement.")

    if not planned_ids or not planned_ids.issubset(approved_ids):
        raise ArtifactError("Visualization plan selection is inconsistent with the approval.")
    items = plan.get("items")
    if not isinstance(items, list) or len(items) != len(planned_ids) * 3:
        raise ArtifactError("Visualization plan does not have three variations per selected concept.")
    coverage: dict[str, set[int]] = {draft_id: set() for draft_id in planned_ids}
    item_by_key = {}
    for item in items:
        if not isinstance(item, dict):
            raise ArtifactError("Visualization plan contains an invalid item.")
        draft_id = item.get("draft_id")
        number = item.get("variation_number")
        unit_key = item.get("unit_key")
        if (
            draft_id not in planned_ids
            or number not in (1, 2, 3)
            or not isinstance(unit_key, str)
            or unit_key in item_by_key
            or item.get("draft_sha256") != approval_by_id[draft_id].get("draft_sha256")
            or item.get("image_prompt_sha256")
            != approval_by_id[draft_id].get("image_prompt_sha256")
        ):
            raise ArtifactError("Visualization plan item is inconsistent with the approval.")
        coverage[draft_id].add(number)
        item_by_key[unit_key] = item
    if any(numbers != {1, 2, 3} for numbers in coverage.values()):
        raise ArtifactError("Visualization plan does not cover every approved variation.")

    checkpoints = run_path / "checkpoints"
    if (
        not checkpoints.is_dir()
        or checkpoints.is_symlink()
        or {path.name for path in checkpoints.iterdir()} != {checkpoint_unit_key}
    ):
        raise ArtifactError("Visualization run must contain exactly its approved checkpoint.")
    checkpoint = checkpoints / checkpoint_unit_key
    lineage, _, lineage_sha256 = _read_json(checkpoint / "lineage.json", "Visualization lineage")
    item = item_by_key.get(lineage.get("unit_key"))
    if (
        item is None
        or lineage.get("unit_key") != checkpoint_unit_key
        or lineage.get("draft_id") != item.get("draft_id")
        or lineage.get("variation_number") != 1
        or lineage.get("variation_name") != "architectural_clarity"
    ):
        raise ArtifactError("Visualization checkpoint identity is inconsistent.")
    expected = {
        "approval_artifact_sha256": hashes["approval"],
        "source_evaluation_sha256": hashes["evaluation"],
        "source_drafts_artifact_sha256": hashes["drafts"],
        "source_draft_sha256": item.get("draft_sha256"),
        "image_prompt_sha256": item.get("image_prompt_sha256"),
        "exact_final_generation_prompt": item.get("final_generation_prompt"),
        "final_generation_prompt_sha256": _sha256(
            str(item.get("final_generation_prompt", "")).encode()
        ),
        "generation_provider": plan.get("provider"),
        "generation_model": plan.get("model"),
        "generation_settings": plan.get("settings"),
        "variation_number": item.get("variation_number"),
        "variation_name": item.get("variation_name"),
    }
    if stage == "creative_refinement_v2":
        draft_id = item["draft_id"]
        expected.update(
            {
                "identity_decomposition_artifact_sha256": hashes["identity_decomposition"],
                "identity_decomposition_concept_sha256": _sha256(
                    _canonical(decomposition_by_id[draft_id], newline=True)
                ),
                "refinement_v2_artifact_sha256": hashes["refinement_v2"],
                "refinement_v2_sha256": refinement_by_id[draft_id].get("refinement_sha256"),
                "refined_v2_prompt_sha256": _sha256(
                    str(refinement_by_id[draft_id].get("concise_provider_prompt", "")).encode()
                ),
            }
        )
    for key, expected_value in expected.items():
        if lineage.get(key) != expected_value:
            raise ArtifactError("Visualization checkpoint lineage is inconsistent.")
    filename = lineage.get("output_asset_filename")
    output_asset_sha256 = lineage.get("output_asset_sha256")
    if filename != "design.png" or not isinstance(output_asset_sha256, str) or not _is_sha256(
        output_asset_sha256
    ):
        raise ArtifactError("Visualization output filename is invalid.")

    metadata = {
        "record_kind": "persisted_visualization_lineage_metadata",
        "development_stage": stage,
        "asset_publicly_available": False,
        "asset_file_verified_at_runtime": False,
        "run_id": manifest.get("run_id"),
        "manifest_sha256": manifest_sha256,
        "plan_sha256": manifest.get("plan_sha256"),
        "lineage_sha256": lineage_sha256,
        "unit_key": lineage.get("unit_key"),
        "variation_number": lineage.get("variation_number"),
        "variation_name": lineage.get("variation_name"),
        "generation_provider": lineage.get("generation_provider"),
        "generation_model": lineage.get("generation_model"),
        "generation_settings": lineage.get("generation_settings"),
        "generation_timestamp": lineage.get("generation_timestamp"),
        "output_asset_filename": filename,
        "output_asset_sha256": output_asset_sha256,
        "source_draft_sha256": lineage.get("source_draft_sha256"),
        "image_prompt_sha256": lineage.get("image_prompt_sha256"),
        "identity_decomposition_artifact_sha256": lineage.get(
            "identity_decomposition_artifact_sha256"
        ),
        "identity_decomposition_concept_sha256": lineage.get(
            "identity_decomposition_concept_sha256"
        ),
        "refinement_v2_artifact_sha256": lineage.get("refinement_v2_artifact_sha256"),
        "refinement_v2_sha256": lineage.get("refinement_v2_sha256"),
        "refined_v2_prompt_sha256": lineage.get("refined_v2_prompt_sha256"),
    }
    return item["draft_id"], metadata


@lru_cache(maxsize=4)
def load_creative_development(
    paths: CreativeDevelopmentPaths = DEFAULT_PATHS,
) -> dict[str, Any]:
    drafts_artifact, _, drafts_sha256 = _read_json(paths.drafts, "Concept drafts")
    evaluation, _, evaluation_sha256 = _read_json(paths.evaluation, "Concept evaluation")
    approval, _, approval_sha256 = _read_json(paths.approval, "Design-generation approval")
    proposals, _, proposals_sha256 = _read_json(paths.identity_proposals, "Identity proposals")
    decomposition, _, decomposition_sha256 = _read_json(
        paths.identity_decomposition, "Identity decomposition"
    )
    refinement, _, refinement_sha256 = _read_json(paths.refinement_v2, "Creative refinement v2")
    hashes = {
        "drafts": drafts_sha256,
        "evaluation": evaluation_sha256,
        "approval": approval_sha256,
        "identity_proposals": proposals_sha256,
        "identity_decomposition": decomposition_sha256,
        "refinement_v2": refinement_sha256,
    }

    drafts = drafts_artifact.get("drafts")
    report = evaluation.get("report")
    approvals = approval.get("approvals")
    proposal_items = proposals.get("concepts")
    decomposition_items = decomposition.get("concepts")
    refinement_items = refinement.get("refinements")
    decisions = evaluation.get("decisions")
    if (
        drafts_artifact.get("artifact_kind") != "ai_generated_concept_drafts_experimental"
        or not isinstance(drafts, list)
        or len(drafts) != 36
        or evaluation.get("artifact_kind") != "private_concept_evaluation"
        or not isinstance(report, dict)
        or report.get("source_sha256") != drafts_sha256
        or approval.get("artifact_kind") != "private_experimental_design_generation_approval"
        or approval.get("source_evaluation_sha256") != evaluation_sha256
        or approval.get("source_drafts_artifact_sha256") != drafts_sha256
        or not isinstance(approvals, list)
        or len(approvals) != 5
        or proposals.get("version") != "concept-identity-input-1"
        or not isinstance(proposal_items, list)
        or decomposition.get("artifact_kind") != "private_concept_identity_decomposition"
        or decomposition.get("source_approval_sha256") != approval_sha256
        or decomposition.get("source_evaluation_sha256") != evaluation_sha256
        or decomposition.get("source_drafts_artifact_sha256") != drafts_sha256
        or decomposition.get("classification_input_sha256") != proposals_sha256
        or not isinstance(decomposition_items, list)
        or refinement.get("artifact_kind") != "private_creative_refinement_v2"
        or refinement.get("source_decomposition_artifact_sha256") != decomposition_sha256
        or refinement.get("source_approval_sha256") != approval_sha256
        or refinement.get("source_evaluation_sha256") != evaluation_sha256
        or refinement.get("source_drafts_artifact_sha256") != drafts_sha256
        or not isinstance(refinement_items, list)
        or not isinstance(decisions, list)
    ):
        raise ArtifactError("Creative-development artifact lineage is inconsistent.")

    expected_ids = [f"draft-{drafts_sha256}-{index:03d}" for index in range(36)]
    approved_ids = [item.get("draft_id") for item in approvals if isinstance(item, dict)]
    approved_set = set(approved_ids)
    if len(approved_ids) != 5 or len(approved_set) != 5 or not approved_set.issubset(expected_ids):
        raise ArtifactError("Creative-development approval set is invalid.")
    approval_by_id = dict(zip(approved_ids, approvals, strict=True))
    decisions_by_id = {
        item.get("draft_id"): item for item in decisions if isinstance(item, dict)
    }
    proposals_by_suffix = {
        item.get("draft_suffix"): item for item in proposal_items if isinstance(item, dict)
    }
    decomposition_by_id = {
        item.get("concept_id"): item for item in decomposition_items if isinstance(item, dict)
    }
    refinement_by_id = {
        item.get("concept_id"): item for item in refinement_items if isinstance(item, dict)
    }
    approved_suffixes = {draft_id.rsplit("-", 1)[-1] for draft_id in approved_set}
    if (
        set(proposals_by_suffix) != approved_suffixes
        or set(decomposition_by_id) != approved_set
        or set(refinement_by_id) != approved_set
        or not approved_set.issubset(decisions_by_id)
    ):
        raise ArtifactError("Creative-development artifacts do not cover the exact approval set.")

    draft_by_id = dict(zip(expected_ids, drafts, strict=True))
    for draft_id in approved_ids:
        draft = draft_by_id[draft_id]
        approved = approval_by_id[draft_id]
        identity = decomposition_by_id[draft_id]
        refined = refinement_by_id[draft_id]
        if (
            not isinstance(draft, dict)
            or approved.get("original_disposition") != decisions_by_id[draft_id].get("disposition")
            or identity.get("source_draft_sha256") != approved.get("draft_sha256")
            or identity.get("category") != draft.get("category")
            or identity.get("requires_re_evaluation") is not True
            or refined.get("category") != draft.get("category")
            or refined.get("source_decomposition_sha256") != _sha256(_canonical(identity))
            or refined.get("requires_re_evaluation") is not True
            or any(refined.get(field) is not False for field in FALSE_VALIDATION_FIELDS)
        ):
            raise ArtifactError("Creative-development concept lineage is inconsistent.")
        for section in ("concept_dna", "hard_product_constraints", "design_variables"):
            claims = identity.get(section)
            if not isinstance(claims, list) or not claims:
                raise ArtifactError("Identity decomposition has invalid claims.")
            for claim in claims:
                value = _resolve_pointer(draft, claim.get("source_field_path"))
                if (
                    value != claim.get("source_excerpt")
                    or not isinstance(value, str)
                    or _sha256(value.encode()) != claim.get("source_claim_sha256")
                ):
                    raise ArtifactError("Identity decomposition claim provenance is inconsistent.")
        dna_ids = {item["claim_id"] for item in identity["concept_dna"]}
        hard_ids = {item["claim_id"] for item in identity["hard_product_constraints"]}
        variables = {item["variable_id"]: item["claim_id"] for item in identity["design_variables"]}
        if (
            {item.get("claim_id") for item in refined.get("dna_preservation_map", [])} != dna_ids
            or {item.get("claim_id") for item in refined.get("hard_constraint_satisfaction_map", [])}
            != hard_ids
            or {
                item.get("variable_id"): item.get("source_claim_id")
                for item in refined.get("variable_transformations", [])
            }
            != variables
            or any(
                item.get("within_permitted_boundary") is not True
                for item in refined.get("variable_transformations", [])
            )
        ):
            raise ArtifactError("Creative refinement does not preserve the identity contract.")
        hash_payload = dict(refined)
        stored_refinement_hash = hash_payload.pop("refinement_sha256", None)
        if stored_refinement_hash != _sha256(_canonical(hash_payload)):
            raise ArtifactError("Creative refinement entry hash is inconsistent.")

    visualizations: dict[str, list[dict[str, Any]]] = {
        draft_id: [] for draft_id in approved_ids
    }
    draft_id_by_suffix = {draft_id.rsplit("-", 1)[-1]: draft_id for draft_id in approved_ids}
    if not {"021", "015", "023", "008", "025"}.issubset(draft_id_by_suffix):
        raise ArtifactError("Creative-development visualization concepts are unavailable.")
    visualization_runs = (
        (paths.base_visualization_run, "base_approved_draft", approved_set,
         "design-021-variation-1"),
        (paths.refinement_v2_visualization_run, "creative_refinement_v2", approved_set,
        "design-021-variation-1"),
        (paths.interlinked_ring_purse_visualization_run, "creative_refinement_v2",
         {draft_id_by_suffix["015"]},
         "design-015-variation-1"),
        (paths.ambient_cuff_blazer_visualization_run, "creative_refinement_v2",
         {draft_id_by_suffix["023"]},
         "design-023-variation-1"),
        (paths.hollow_column_brief_visualization_run, "creative_refinement_v2",
         {draft_id_by_suffix["008"]},
         "design-008-variation-1"),
        (paths.kinetic_bias_skirt_visualization_run, "creative_refinement_v2",
         {draft_id_by_suffix["025"]},
         "design-025-variation-1"),
    )
    for run_path, stage, planned_ids, checkpoint_unit_key in visualization_runs:
        draft_id, metadata = _validate_visualization(
            run_path=run_path,
            stage=stage,
            hashes=hashes,
            approved_ids=approved_set,
            approval_by_id=approval_by_id,
            decomposition_by_id=decomposition_by_id,
            refinement_by_id=refinement_by_id,
            planned_ids=planned_ids,
            checkpoint_unit_key=checkpoint_unit_key,
        )
        visualizations[draft_id].append(metadata)

    concepts = []
    for draft_id in approved_ids:
        draft = draft_by_id[draft_id]
        concepts.append(
            {
                "draft_id": draft_id,
                "product_name": draft.get("product_name"),
                "category": draft.get("category"),
                "evaluation_decision": decisions_by_id[draft_id],
                "experimental_design_generation_approval": approval_by_id[draft_id],
                "identity_proposal": proposals_by_suffix[draft_id.rsplit("-", 1)[-1]],
                "identity_decomposition": decomposition_by_id[draft_id],
                "creative_refinement_v2": refinement_by_id[draft_id],
                "visualizations": visualizations[draft_id],
            }
        )

    return {
        "artifact_kind": "creative_development_read_only_projection",
        "private_experimental_development": True,
        "fictional_study_label": drafts_artifact.get("fictional_study_label"),
        "non_affiliation_disclaimer": drafts_artifact.get("non_affiliation_disclaimer"),
        "provenance": {
            "source_drafts_sha256": drafts_sha256,
            "evaluation_run_id": EVALUATION_RUN_ID,
            "evaluation_sha256": evaluation_sha256,
            "approval_sha256": approval_sha256,
            "identity_proposals_sha256": proposals_sha256,
            "identity_decomposition_sha256": decomposition_sha256,
            "creative_refinement_v2_sha256": refinement_sha256,
            "creative_refinement_v2_version": refinement.get("version"),
            "creative_refinement_v2_created_at": refinement.get("created_at"),
        },
        "concepts": concepts,
    }
