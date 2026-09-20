"""Read-only projection of the completed v21 independent concept evaluation."""

from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.model_loader import ArtifactError


ROOT = Path(__file__).resolve().parent.parent
CONCEPT_DRAFTS_PATH = (
    ROOT / "data" / "experiments" / "concept_originator" / "first_hf_concept_drafts.json"
)
EVALUATION_RUN_ID = "evaluation_20260917_gpt_oss_pair_two_sided_v21"
EVALUATION_PATH = (
    ROOT
    / "data"
    / "experiments"
    / "concept_originator"
    / "evaluations"
    / EVALUATION_RUN_ID
    / "evaluation.json"
)
APPROVAL_PATH = (
    ROOT
    / "data"
    / "experiments"
    / "concept_originator"
    / "design_generation_approvals"
    / f"{EVALUATION_RUN_ID}_initial_five.json"
)


def _read_json(path: Path, label: str) -> tuple[dict[str, Any], str]:
    if not path.is_file():
        raise ArtifactError(f"{label} artifact is unavailable.")
    try:
        raw = path.read_bytes()
        value = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"{label} artifact could not be loaded.") from exc
    if not isinstance(value, dict):
        raise ArtifactError(f"{label} artifact must be an object.")
    return value, hashlib.sha256(raw).hexdigest()


@lru_cache(maxsize=1)
def load_evaluated_concepts() -> dict[str, Any]:
    """Return the immutable v21 evaluation joined to its source drafts and approval record."""
    drafts_artifact, drafts_sha256 = _read_json(CONCEPT_DRAFTS_PATH, "Concept drafts")
    evaluation, evaluation_sha256 = _read_json(EVALUATION_PATH, "Concept evaluation")
    approval, _ = _read_json(APPROVAL_PATH, "Design-generation approval")

    drafts = drafts_artifact.get("drafts")
    report = evaluation.get("report")
    decisions = evaluation.get("decisions")
    selection = evaluation.get("selection")
    approvals = approval.get("approvals")
    if (
        drafts_artifact.get("artifact_kind") != "ai_generated_concept_drafts_experimental"
        or not isinstance(drafts, list)
        or len(drafts) != 36
        or evaluation.get("artifact_kind") != "private_concept_evaluation"
        or not isinstance(report, dict)
        or not isinstance(report.get("assessments"), list)
        or len(report["assessments"]) != 36
        or not isinstance(decisions, list)
        or len(decisions) != 36
        or not isinstance(selection, dict)
        or approval.get("artifact_kind") != "private_experimental_design_generation_approval"
        or not isinstance(approvals, list)
    ):
        raise ArtifactError("The v21 evaluated-concepts artifacts have an invalid shape.")
    if report.get("source_sha256") != drafts_sha256:
        raise ArtifactError("The v21 evaluation does not match the concept draft artifact.")
    if (
        approval.get("source_run_id") != EVALUATION_RUN_ID
        or approval.get("source_evaluation_sha256") != evaluation_sha256
        or approval.get("source_drafts_artifact_sha256") != drafts_sha256
    ):
        raise ArtifactError("The v21 approval does not match the evaluation lineage.")

    assessments = report["assessments"]
    draft_ids = [item.get("draft_id") for item in assessments if isinstance(item, dict)]
    decision_by_id = {
        item.get("draft_id"): item for item in decisions if isinstance(item, dict)
    }
    approval_by_id = {
        item.get("draft_id"): item for item in approvals if isinstance(item, dict)
    }
    expected_draft_ids = [
        f"draft-{drafts_sha256}-{index:03d}" for index in range(len(drafts))
    ]
    if (
        draft_ids != expected_draft_ids
        or len(set(draft_ids)) != 36
        or set(decision_by_id) != set(draft_ids)
        or len(approval_by_id) != len(approvals)
        or not set(approval_by_id).issubset(draft_ids)
    ):
        raise ArtifactError("The v21 evaluation contains inconsistent draft identifiers.")

    evaluator_selected_ids = selection.get("portfolio_ids")
    if not isinstance(evaluator_selected_ids, list):
        raise ArtifactError("The v21 evaluator selection is invalid.")
    selected = set(evaluator_selected_ids)
    if len(selected) != len(evaluator_selected_ids) or not selected.issubset(draft_ids):
        raise ArtifactError("The v21 evaluator selection contains invalid draft identifiers.")
    concepts = []
    for draft_id, draft, assessment in zip(draft_ids, drafts, assessments, strict=True):
        if not isinstance(draft, dict):
            raise ArtifactError("The v21 draft source contains an invalid draft.")
        decision = decision_by_id[draft_id]
        approval_record = approval_by_id.get(draft_id)
        concepts.append(
            {
                "draft_id": draft_id,
                "product_name": draft.get("product_name"),
                "category": draft.get("category"),
                "evaluation_status": decision.get("disposition"),
                "structural_evaluation": assessment.get("structural"),
                "contextual_evaluation": assessment.get("contextual"),
                "evaluation_decision": decision,
                "evaluator_selected": draft_id in selected,
                "approved_for_experimental_design_generation": approval_record is not None,
                "experimental_design_generation_approval": approval_record,
                "rejection_reasons": (
                    decision.get("reasons", [])
                    if decision.get("disposition") == "reject"
                    else []
                ),
            }
        )

    return {
        "artifact_kind": "evaluated_concepts_read_only_projection",
        "experimental": evaluation.get("experimental"),
        "is_synthetic_input": evaluation.get("is_synthetic_input"),
        "fictional_study_label": drafts_artifact.get("fictional_study_label"),
        "non_affiliation_disclaimer": drafts_artifact.get("non_affiliation_disclaimer"),
        "evaluation_provenance": {
            "run_id": EVALUATION_RUN_ID,
            "source_drafts_sha256": drafts_sha256,
            "evaluation_sha256": evaluation_sha256,
            "evaluator": report.get("evaluator"),
            "rubric_version": report.get("rubric_version"),
            "schema_version": report.get("schema_version"),
            "evaluated_at": report.get("evaluated_at"),
        },
        "evaluator_selection": selection,
        "approval_provenance": {
            "artifact_kind": approval.get("artifact_kind"),
            "version": approval.get("version"),
            "purpose": approval.get("purpose"),
            "approved_at": approval.get("approved_at"),
            "approved_by": approval.get("approved_by"),
            "implies_evaluator_eligibility": approval.get("implies_evaluator_eligibility"),
            "commercially_validated": approval.get("commercially_validated"),
            "production_feasible": approval.get("production_feasible"),
            "production_collection": approval.get("production_collection"),
        },
        "concepts": concepts,
    }
