"""Deterministic construction and fail-closed loading of query/linkage artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .models import (
    ConceptQueryBundle,
    ConceptQueryBundleArtifact,
    ConceptSignalLinkage,
    ConceptSignalLinkageArtifact,
    EvidenceRole,
    PersistedAttributeReference,
    QueryCandidate,
    QueryReviewState,
    QueryReviewEvent,
)

REFINEMENT_PATH = Path("data/experiments/concept_originator/creative_refinements/evaluation_20260917_gpt_oss_pair_two_sided_v21_creative_refinement_v2.json")
DRAFTS_PATH = Path("data/experiments/concept_originator/first_hf_concept_drafts.json")
RULE_VERSION = "concept-query-rules-1.0"
CATEGORY_TAXONOMY_VERSION = "fashion-product-category-1.0"
HUMAN_REVIEW_VERSION = "phase-1-human-query-review-v1"
HUMAN_REVIEWED_AT = "2026-09-21T00:00:00+03:00"

# Candidate phrases are deliberately review-gated. Each rule identifies the exact
# persisted v2 field(s) a reviewer must inspect; it does not assert market equivalence.
RULES: dict[str, tuple[tuple[str, str, tuple[tuple[str, str], ...]], ...]] = {
    "021": (
        ("monk strap footwear", "craftsmanship_construction", (("hard_constraint_satisfaction_map", "0"),)),
        ("woven leather footwear", "craftsmanship_construction", (("dna_preservation_map", "0"),)),
        ("narrow last footwear", "silhouette_form", (("variable_transformations", "2"),)),
        ("calfskin footwear", "material", (("variable_transformations", "3"),)),
        ("butter yellow footwear", "color", (("variable_transformations", "3"),)),
    ),
    "015": (
        ("leather ring clutch", "craftsmanship_construction", (("dna_preservation_map", "0"), ("variable_transformations", "1"))),
        ("vertical leather clutch", "silhouette_form", (("variable_transformations", "1"),)),
        ("basket clutch", "silhouette_form", (("variable_transformations", "1"),)),
        ("reconfigurable leather clutch", "consumer_behavior", (("dna_preservation_map", "0"), ("variable_transformations", "1"))),
        ("blue leather clutch", "color", (("variable_transformations", "2"), ("variable_transformations", "1"))),
    ),
    "023": (
        ("suspended shoulder blazer", "craftsmanship_construction", (("dna_preservation_map", "0"),)),
        ("floating shoulder blazer", "silhouette_form", (("variable_transformations", "1"),)),
        ("long lean blazer", "silhouette_form", (("variable_transformations", "1"),)),
        ("olive wool blazer", "material", (("variable_transformations", "2"),)),
        ("quilted silk blazer", "material", (("variable_transformations", "2"),)),
    ),
    "008": (
        ("architectural briefcase", "silhouette_form", (("variable_transformations", "2"),)),
        ("slim vertical briefcase", "silhouette_form", (("variable_transformations", "2"),)),
        ("panel constructed briefcase", "craftsmanship_construction", (("dna_preservation_map", "0"),)),
        ("goatskin briefcase", "material", (("variable_transformations", "0"),)),
        ("electric blue briefcase", "color", (("variable_transformations", "2"),)),
        ("flat folder briefcase", "consumer_behavior", (("dna_preservation_map", "0"),)),
    ),
    "025": (
        ("bias cut silk skirt", "craftsmanship_construction", (("dna_preservation_map", "0"), ("variable_transformations", "2"))),
        ("spiral panel skirt", "craftsmanship_construction", (("dna_preservation_map", "1"),)),
        ("column skirt", "silhouette_form", (("variable_transformations", "1"),)),
        ("asymmetric volume skirt", "silhouette_form", (("variable_transformations", "1"),)),
        ("off-white silk skirt", "material", (("variable_transformations", "2"),)),
        ("butter yellow skirt", "color", (("variable_transformations", "2"),)),
    ),
}


def _canonical(value: Any) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _sha(value: Any) -> str:
    return hashlib.sha256(value if isinstance(value, bytes) else _canonical(value)).hexdigest()


def _read(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def _ref(refinement_path: Path, artifact_hash: str, refinement: dict[str, Any], index: int,
         section: str, item: str) -> PersistedAttributeReference:
    pointer = f"/refinements/{index}/{section}" if item == "" else f"/refinements/{index}/{section}/{item}"
    value: Any = refinement[section] if item == "" else refinement[section][int(item)]
    if isinstance(value, dict):
        value = value.get("preserved_manifestation", value.get("transformation"))
    return PersistedAttributeReference(
        artifact_path=refinement_path.as_posix(), artifact_sha256=artifact_hash,
        json_pointer=pointer, attribute_value=value, attribute_value_sha256=_sha(value.encode()),
        refinement_sha256=refinement["refinement_sha256"],
    )


def _stable_id(prefix: str, payload: Any) -> str:
    return f"{prefix}-{_sha(payload)}"


def build_candidate_artifacts(
    refinement_path: Path = REFINEMENT_PATH, drafts_path: Path = DRAFTS_PATH
) -> tuple[ConceptQueryBundleArtifact, ConceptSignalLinkageArtifact]:
    refinements, refinement_hash = _read(refinement_path)
    drafts, drafts_hash = _read(drafts_path)
    if refinements.get("version") != "creative-refinement-2":
        raise ValueError("stale or unsupported creative refinement version")
    if refinements.get("source_drafts_artifact_sha256") != drafts_hash:
        raise ValueError("creative refinement does not match the current draft artifact")

    bundles = []
    linkage_specs: list[tuple[ConceptQueryBundle, QueryCandidate, QueryReviewState, str | None]] = []
    for index, refinement in enumerate(refinements["refinements"]):
        entry_payload = dict(refinement)
        entry_hash = entry_payload.pop("refinement_sha256", None)
        if entry_hash != _sha(entry_payload):
            raise ValueError("creative refinement entry hash mismatch")
        suffix = refinement["concept_id"].rsplit("-", 1)[-1]
        if suffix not in RULES:
            raise ValueError(f"unsupported approved concept: {refinement['concept_id']}")
        draft = drafts["drafts"][int(suffix)]
        if draft["category"] != refinement["category"]:
            raise ValueError("creative refinement category does not match source draft")
        category_text = refinement["category"].casefold()
        category_ref = _ref(refinement_path, refinement_hash, refinement, index, "category", "")
        candidate_specs = [(category_text, "product_category", (category_ref,), "exact-category-normalization-v1")]
        for text, signal_type, locations in RULES[suffix]:
            refs = tuple(_ref(refinement_path, refinement_hash, refinement, index, section, item)
                         for section, item in locations)
            candidate_specs.append((text, signal_type, refs, "review-required-semantic-phrase-v1"))

        queries = []
        for text, signal_type, refs, rule_id in candidate_specs:
            payload = {"concept_id": refinement["concept_id"], "query_text": text,
                       "signal_type": signal_type, "provenance": [r.model_dump(mode="json") for r in refs],
                       "rule": rule_id, "version": RULE_VERSION}
            queries.append(QueryCandidate(
                query_id=_stable_id("query", payload), query_text=text, signal_type=signal_type,
                derivation_rule_id=rule_id, derivation_rule_version=RULE_VERSION, provenance=refs,
            ))
        bundle_payload = {"concept_id": refinement["concept_id"], "refinement_sha256": refinement["refinement_sha256"],
                          "query_ids": [q.query_id for q in queries], "version": "concept-query-bundle-v1"}
        bundle = ConceptQueryBundle(
            bundle_id=_stable_id("bundle", bundle_payload), concept_id=refinement["concept_id"],
            product_name=draft["product_name"], category=refinement["category"],
            refinement_sha256=refinement["refinement_sha256"], queries=tuple(queries),
        )
        bundles.append(bundle)
        for query in queries:
            exact = query.derivation_rule_id == "exact-category-normalization-v1"
            linkage_specs.append((bundle, query, QueryReviewState.REVIEWED if exact else QueryReviewState.CANDIDATE,
                                  f"category:{category_text.replace('-', '_').replace(' ', '_')}" if exact else None))

    bundle_artifact = ConceptQueryBundleArtifact(
        created_at=refinements["created_at"], source_refinement_path=refinement_path.as_posix(),
        source_refinement_artifact_sha256=refinement_hash,
        source_drafts_artifact_sha256=drafts_hash, bundles=tuple(bundles),
    )
    bundle_hash = _sha(bundle_artifact)
    linkages = []
    for bundle, query, state, code in linkage_specs:
        payload = {"bundle": bundle.bundle_id, "query": query.query_id, "state": state.value,
                   "version": "creative-refinement-v2-linkages-v1"}
        linkages.append(ConceptSignalLinkage(
            linkage_id=_stable_id("linkage", payload), concept_id=bundle.concept_id,
            bundle_id=bundle.bundle_id, query_id=query.query_id, review_state=state,
            eligible_for_market_evidence=state == QueryReviewState.REVIEWED,
            canonical_taxonomy_code=code,
            review_basis=f"deterministic exact category mapping; taxonomy={CATEGORY_TAXONOMY_VERSION}" if code else None,
        ))
    linkage_artifact = ConceptSignalLinkageArtifact(
        created_at=refinements["created_at"], source_query_bundle_sha256=bundle_hash,
        source_refinement_artifact_sha256=refinement_hash, linkages=tuple(linkages),
    )
    return bundle_artifact, linkage_artifact


REVIEW_DECISIONS = {
    "reconfigurable leather clutch": QueryReviewState.AMBIGUOUS,
    "flat folder briefcase": QueryReviewState.AMBIGUOUS,
}


def build_reviewed_linkage_artifact(
    bundle_artifact: ConceptQueryBundleArtifact,
    initial_linkages: ConceptSignalLinkageArtifact,
    initial_linkage_artifact_sha256: str,
) -> ConceptSignalLinkageArtifact:
    """Apply the approved human review without mutating the immutable v1 records."""
    if initial_linkages.artifact_version != "creative-refinement-v2-linkages-v1":
        raise ValueError("human review must be based on the immutable v1 linkage artifact")
    if initial_linkages.source_query_bundle_sha256 != _sha(bundle_artifact):
        raise ValueError("linkage review source query bundle hash mismatch")
    if len(initial_linkage_artifact_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in initial_linkage_artifact_sha256
    ):
        raise ValueError("invalid immutable v1 linkage artifact hash")
    queries = {q.query_id: q for bundle in bundle_artifact.bundles for q in bundle.queries}
    concept_names = {bundle.concept_id: bundle.product_name.casefold() for bundle in bundle_artifact.bundles}
    reviewed = []
    for previous in initial_linkages.linkages:
        query = queries.get(previous.query_id)
        if query is None or previous.concept_id not in concept_names:
            raise ValueError("linkage review references an unsupported query or concept")
        if concept_names[previous.concept_id] in query.query_text.casefold():
            raise ValueError("invented concept names cannot be reviewed market queries")
        decision = REVIEW_DECISIONS.get(query.query_text, QueryReviewState.REVIEWED)
        role = EvidenceRole.BASELINE_CATEGORY if query.signal_type.value == "product_category" else EvidenceRole.CONCEPT_ATTRIBUTE
        code = (f"category:{query.query_text.replace('-', '_').replace(' ', '_')}"
                if role == EvidenceRole.BASELINE_CATEGORY else f"reviewed_query:{query.query_id.removeprefix('query-')}")
        rationale = (
            "Accepted baseline category representation only; specificity, evidence quality, search volume, and Demand Potential contribution are not established."
            if role == EvidenceRole.BASELINE_CATEGORY else
            "Human-reviewed as an acceptable representation of the cited persisted Creative Refinement v2 attribute; no market demand or evidence quality is asserted."
        )
        if decision == QueryReviewState.AMBIGUOUS:
            code = None
            rationale = "Meaning or likely search intent is ambiguous; retained for audit history but ineligible for market evidence collection."
        event = QueryReviewEvent(
            review_version=HUMAN_REVIEW_VERSION, reviewed_at=HUMAN_REVIEWED_AT,
            reviewer="human-approved-project-review", previous_state=previous.review_state,
            decision=decision, rationale=rationale,
        )
        reviewed.append(previous.model_copy(update={
            "review_state": decision,
            "eligible_for_market_evidence": decision == QueryReviewState.REVIEWED,
            "canonical_taxonomy_code": code,
            "review_basis": rationale if decision == QueryReviewState.REVIEWED else None,
            "evidence_role": role,
            "demand_contribution_assessed": False,
            "review_history": previous.review_history + (event,),
        }))
    return ConceptSignalLinkageArtifact(
        artifact_version="creative-refinement-v2-linkages-v2",
        created_at=HUMAN_REVIEWED_AT,
        source_query_bundle_sha256=_sha(bundle_artifact),
        source_refinement_artifact_sha256=bundle_artifact.source_refinement_artifact_sha256,
        previous_linkage_artifact_sha256=initial_linkage_artifact_sha256,
        linkages=tuple(reviewed),
    )


def persist_immutable_artifact(path: Path, artifact: ConceptQueryBundleArtifact | ConceptSignalLinkageArtifact) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(json.dumps(artifact.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False).encode() + b"\n")


def load_and_validate_artifacts(bundle_path: Path, linkage_path: Path,
                                refinement_path: Path = REFINEMENT_PATH,
                                drafts_path: Path = DRAFTS_PATH) -> tuple[ConceptQueryBundleArtifact, ConceptSignalLinkageArtifact]:
    bundle = ConceptQueryBundleArtifact.model_validate_json(bundle_path.read_bytes())
    linkage = ConceptSignalLinkageArtifact.model_validate_json(linkage_path.read_bytes())
    expected_bundle, expected_linkage = build_candidate_artifacts(refinement_path, drafts_path)
    if bundle != expected_bundle:
        raise ValueError("query bundle is stale, unsupported, or has failed provenance validation")
    if linkage != expected_linkage:
        raise ValueError("concept linkage is stale, unsupported, or has failed provenance validation")
    return bundle, linkage
