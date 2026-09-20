import hashlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.demand_intelligence import (
    ConceptQueryBundle,
    ConceptSignalLinkage,
    QueryReviewState,
    build_candidate_artifacts,
    build_reviewed_linkage_artifact,
    load_and_validate_artifacts,
    persist_immutable_artifact,
)

BUNDLE_PATH = Path("data/market_evidence/concept_query_bundles/creative_refinement_v2_query_bundles_v1.json")
LINKAGE_PATH = Path("data/market_evidence/concept_signal_linkages/creative_refinement_v2_signal_linkages_v1.json")
REVIEWED_LINKAGE_PATH = Path("data/market_evidence/concept_signal_linkages/creative_refinement_v2_signal_linkages_v2.json")
REFINEMENT_PATH = Path("data/experiments/concept_originator/creative_refinements/evaluation_20260917_gpt_oss_pair_two_sided_v21_creative_refinement_v2.json")
DRAFTS_PATH = Path("data/experiments/concept_originator/first_hf_concept_drafts.json")


def reviewed_artifact():
    bundles, initial = build_candidate_artifacts()
    v1_hash = hashlib.sha256(LINKAGE_PATH.read_bytes()).hexdigest()
    return bundles, initial, build_reviewed_linkage_artifact(bundles, initial, v1_hash)


def test_generated_artifacts_are_deterministic_and_persisted_exactly():
    first = build_candidate_artifacts()
    second = build_candidate_artifacts()
    assert first == second
    loaded = load_and_validate_artifacts(BUNDLE_PATH, LINKAGE_PATH)
    assert loaded == first
    assert len(loaded[0].bundles) == 5


def test_every_query_has_resolvable_hashed_provenance():
    bundles, _ = build_candidate_artifacts()
    source = json.loads(REFINEMENT_PATH.read_bytes())
    source_hash = hashlib.sha256(REFINEMENT_PATH.read_bytes()).hexdigest()
    for bundle in bundles.bundles:
        assert bundle.refinement_version == source["version"]
        for query in bundle.queries:
            for ref in query.provenance:
                assert ref.artifact_sha256 == source_hash
                value = source
                for token in ref.json_pointer.strip("/").split("/"):
                    value = value[int(token)] if isinstance(value, list) else value[token]
                if isinstance(value, dict):
                    value = value.get("preserved_manifestation", value.get("transformation"))
                assert value == ref.attribute_value
                assert hashlib.sha256(value.encode()).hexdigest() == ref.attribute_value_sha256


def test_only_exact_category_mappings_are_reviewed_and_eligible():
    bundles, links = build_candidate_artifacts()
    by_query = {q.query_id: q for b in bundles.bundles for q in b.queries}
    reviewed = [link for link in links.linkages if link.review_state == QueryReviewState.REVIEWED]
    assert len(reviewed) == 5
    assert all(by_query[link.query_id].derivation_rule_id == "exact-category-normalization-v1" for link in reviewed)
    assert all(link.eligible_for_market_evidence for link in reviewed)
    assert all(not link.eligible_for_market_evidence for link in links.linkages if link not in reviewed)


def test_review_eligibility_fails_closed():
    _, links = build_candidate_artifacts()
    candidate = next(link for link in links.linkages if link.review_state == QueryReviewState.CANDIDATE)
    with pytest.raises(ValidationError, match="only reviewed"):
        ConceptSignalLinkage(**(candidate.model_dump() | {"eligible_for_market_evidence": True}))


def test_invented_concept_name_is_excluded():
    bundles, _ = build_candidate_artifacts()
    bundle = bundles.bundles[0]
    query = bundle.queries[0].model_copy(update={"query_text": bundle.product_name})
    with pytest.raises(ValidationError, match="invented concept names"):
        ConceptQueryBundle(**(bundle.model_dump() | {"queries": [query]}))


def test_stale_refinement_version_and_tampered_source_fail(tmp_path):
    stale = json.loads(REFINEMENT_PATH.read_bytes())
    stale["version"] = "creative-refinement-1"
    stale_path = tmp_path / "stale.json"
    stale_path.write_text(json.dumps(stale))
    with pytest.raises(ValueError, match="stale or unsupported"):
        build_candidate_artifacts(stale_path, DRAFTS_PATH)

    tampered = json.loads(REFINEMENT_PATH.read_bytes())
    tampered["refinements"][0]["category"] = "Invented Category"
    tampered_path = tmp_path / "tampered.json"
    tampered_path.write_text(json.dumps(tampered))
    with pytest.raises(ValueError, match="entry hash mismatch"):
        build_candidate_artifacts(tampered_path, DRAFTS_PATH)


def test_unsupported_query_or_tampered_artifact_fails(tmp_path):
    bundle_data = json.loads(BUNDLE_PATH.read_bytes())
    bundle_data["bundles"][0]["queries"][0]["query_text"] = "unsupported invented query"
    bad_bundle = tmp_path / "bundle.json"
    bad_bundle.write_text(json.dumps(bundle_data))
    with pytest.raises(ValueError, match="failed provenance"):
        load_and_validate_artifacts(bad_bundle, LINKAGE_PATH)


def test_persistence_is_immutable(tmp_path):
    bundles, _ = build_candidate_artifacts()
    target = tmp_path / "artifact.json"
    persist_immutable_artifact(target, bundles)
    with pytest.raises(FileExistsError):
        persist_immutable_artifact(target, bundles)


def test_human_review_v2_preserves_history_and_eligibility():
    bundles, initial, reviewed = reviewed_artifact()
    persisted = type(reviewed).model_validate_json(REVIEWED_LINKAGE_PATH.read_bytes())
    assert persisted == reviewed
    assert reviewed.previous_linkage_artifact_sha256 == hashlib.sha256(LINKAGE_PATH.read_bytes()).hexdigest()
    states = [link.review_state for link in reviewed.linkages]
    assert states.count(QueryReviewState.REVIEWED) == 30
    assert states.count(QueryReviewState.AMBIGUOUS) == 2
    assert all(link.eligible_for_market_evidence == (link.review_state == QueryReviewState.REVIEWED)
               for link in reviewed.linkages)
    assert all(link.demand_contribution_assessed is False for link in reviewed.linkages)
    assert all(len(link.review_history) == 1 for link in reviewed.linkages)


def test_ambiguous_decisions_remain_ineligible_and_category_is_baseline_only():
    bundles, initial, reviewed = reviewed_artifact()
    queries = {q.query_id: q for bundle in bundles.bundles for q in bundle.queries}
    ambiguous = [queries[link.query_id].query_text for link in reviewed.linkages
                 if link.review_state == QueryReviewState.AMBIGUOUS]
    assert sorted(ambiguous) == ["flat folder briefcase", "reconfigurable leather clutch"]
    assert all(not link.eligible_for_market_evidence for link in reviewed.linkages
               if link.review_state == QueryReviewState.AMBIGUOUS)
    category_links = [link for link in reviewed.linkages if link.evidence_role.value == "baseline_category"]
    assert len(category_links) == 5
    assert all("Demand Potential contribution are not established" in link.review_basis
               for link in category_links)


def test_reviewed_queries_keep_exact_candidate_provenance_and_exclude_names():
    bundles, initial, reviewed = reviewed_artifact()
    query_by_id = {q.query_id: q for bundle in bundles.bundles for q in bundle.queries}
    names = {bundle.concept_id: bundle.product_name.casefold() for bundle in bundles.bundles}
    for link in reviewed.linkages:
        query = query_by_id[link.query_id]
        assert query.provenance
        assert names[link.concept_id] not in query.query_text.casefold()
