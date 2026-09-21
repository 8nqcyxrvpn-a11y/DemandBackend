import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.demand_intelligence import (
    EvidenceAvailability,
    GoogleAdsHistoricalMetricsTransport,
    MarketQueryProvenance,
    MarketScope,
    MonthlyHistoricalObservation,
    ProviderResponseMetadata,
    RawMarketEvidenceArtifact,
    RawMarketObservation,
    RequestedTimeWindow,
    build_google_ads_plan,
    load_market_evidence_context,
    normalize_raw_observation,
    persist_immutable_market_artifact,
    validate_raw_market_artifact,
)
from app.demand_intelligence.market_evidence import (
    BUNDLE_PATH,
    LINKAGE_V1_PATH,
    LINKAGE_V2_PATH,
)
from app.demand_intelligence.query_bundles import DRAFTS_PATH, REFINEMENT_PATH

NOW = datetime(2026, 9, 22, tzinfo=timezone.utc)
MONK_QUERY_ID = "query-3134ba1de1b6c565e6a6adb3e520998456b011086c740242e20d4b874380274e"
AMBIGUOUS_QUERY_TEXTS = {"reconfigurable leather clutch", "flat folder briefcase"}


def scope():
    return MarketScope(
        geography_id="geoTargetConstants/2840",
        geography_name="United States",
        geography_level="country",
        language_id="languageConstants/1000",
        language_name="English",
        network="GOOGLE_SEARCH",
    )


def window():
    return RequestedTimeWindow(label="provider default trailing 12 months")


def response_payload():
    return json.dumps({"results": [{"text": "monk strap footwear"}]}, separators=(",", ":"))


def raw_observation(**changes):
    context = load_market_evidence_context()
    raw_json = response_payload()
    raw_hash = hashlib.sha256(raw_json.encode()).hexdigest()
    values = {
        "observation_id": "raw-market-" + "1" * 64,
        "provider": "google_ads_keyword_planner",
        "source_id": "google-ads-keyword-planner-v25",
        "provenance": context.provenance_for(MONK_QUERY_ID),
        "scope": scope(),
        "collected_at": NOW,
        "requested_time_window": window(),
        "availability": "observed",
        "provider_keyword_text": "monk strap footwear",
        "average_monthly_searches": 10,
        "monthly_history": [{"year": 2026, "month": 8, "searches": 10}],
        "competition_level": "LOW",
        "competition_index": 12,
        "response_metadata": {
            "provider_operation": "GenerateKeywordHistoricalMetrics",
            "api_version": "v25",
            "http_status": 200,
            "request_id": "safe-request-id",
            "received_at": NOW,
            "raw_response_sha256": raw_hash,
        },
    }
    values.update(changes)
    return RawMarketObservation(**values)


def raw_artifact(observation=None, **changes):
    raw_json = response_payload()
    raw_hash = hashlib.sha256(raw_json.encode()).hexdigest()
    context = load_market_evidence_context()
    values = {
        "artifact_version": "google-ads-pilot-v1",
        "run_id": "google_ads_test_001",
        "created_at": NOW,
        "provider": "google_ads_keyword_planner",
        "query_bundle_artifact_sha256": context.bundle_artifact_sha256,
        "reviewed_linkage_artifact_sha256": context.linkage_artifact_sha256,
        "refinement_artifact_sha256": context.bundles.source_refinement_artifact_sha256,
        "raw_provider_response_json": raw_json,
        "raw_provider_response_sha256": raw_hash,
        "observations": [observation or raw_observation()],
    }
    values.update(changes)
    return RawMarketEvidenceArtifact(**values)


def test_context_exposes_only_30_reviewed_queries_and_rejects_ambiguous():
    context = load_market_evidence_context()
    eligible = [item for item in context.reviewed_linkages.linkages if item.eligible_for_market_evidence]
    assert len(eligible) == 30
    bundle_queries = {q.query_text: q.query_id for bundle in context.bundles.bundles for q in bundle.queries}
    for text in AMBIGUOUS_QUERY_TEXTS:
        with pytest.raises(ValueError, match="ambiguous or ineligible"):
            context.provenance_for(bundle_queries[text])


def test_provenance_chain_reaches_exact_refinement_attributes():
    context = load_market_evidence_context()
    provenance = context.provenance_for(MONK_QUERY_ID, "monk strap footwear")
    assert provenance.query_text == "monk strap footwear"
    assert provenance.concept_id.endswith("-021")
    assert provenance.refinement_version == "creative-refinement-2"
    assert provenance.refinement_artifact_sha256 == context.bundles.source_refinement_artifact_sha256
    assert provenance.attribute_references[0].json_pointer == "/refinements/0/hard_constraint_satisfaction_map/0"


def test_unknown_or_altered_query_fails_closed():
    context = load_market_evidence_context()
    with pytest.raises(ValueError, match="unknown"):
        context.provenance_for("query-" + "0" * 64)
    with pytest.raises(ValueError, match="differs"):
        context.provenance_for(MONK_QUERY_ID, "altered query")


def test_invented_concept_name_is_rejected_in_observation_provenance():
    provenance = load_market_evidence_context().provenance_for(MONK_QUERY_ID)
    with pytest.raises(ValidationError, match="invented concept names"):
        MarketQueryProvenance(**(
            provenance.model_dump() | {"query_text": provenance.concept_product_name}
        ))


def test_stale_refinement_and_tampered_phase1_hashes_fail(tmp_path):
    stale = json.loads(REFINEMENT_PATH.read_bytes())
    stale["version"] = "creative-refinement-1"
    stale_path = tmp_path / "stale-refinement.json"
    stale_path.write_text(json.dumps(stale))
    with pytest.raises(ValueError, match="stale or unsupported"):
        load_market_evidence_context(
            BUNDLE_PATH, LINKAGE_V1_PATH, LINKAGE_V2_PATH, stale_path, DRAFTS_PATH
        )

    tampered = json.loads(BUNDLE_PATH.read_bytes())
    tampered["bundles"][0]["queries"][0]["query_text"] = "invented market phrase"
    tampered_path = tmp_path / "tampered-bundle.json"
    tampered_path.write_text(json.dumps(tampered))
    with pytest.raises(ValueError, match="failed provenance"):
        load_market_evidence_context(
            tampered_path, LINKAGE_V1_PATH, LINKAGE_V2_PATH, REFINEMENT_PATH, DRAFTS_PATH
        )


@pytest.mark.parametrize("state", [
    "no_data", "suppressed", "unavailable", "provider_error", "permission_denied"
])
def test_missing_or_failed_states_never_become_zero(state):
    metadata = raw_observation().response_metadata.model_dump()
    if state in {"provider_error", "permission_denied"}:
        metadata["provider_error_status"] = state.upper()
    observation = raw_observation(
        availability=state,
        average_monthly_searches=None,
        monthly_history=[],
        competition_level=None,
        competition_index=None,
        response_metadata=metadata,
    )
    normalized = normalize_raw_observation(observation, "a" * 64)
    assert normalized.availability.value == state
    assert normalized.average_monthly_searches is None
    assert normalized.monthly_history == ()


def test_explicit_provider_zero_is_not_confused_with_missing():
    observed = raw_observation(average_monthly_searches=0, monthly_history=[])
    assert observed.availability == EvidenceAvailability.OBSERVED
    assert observed.average_monthly_searches == 0
    with pytest.raises(ValidationError, match="non-observed"):
        raw_observation(availability="no_data", average_monthly_searches=0, monthly_history=[])


def test_malformed_observations_fail_closed():
    with pytest.raises(ValidationError, match="requires an explicitly returned metric"):
        raw_observation(
            average_monthly_searches=None, monthly_history=[], competition_level=None,
            competition_index=None,
        )
    with pytest.raises(ValidationError, match="duplicate monthly"):
        raw_observation(monthly_history=[
            {"year": 2026, "month": 8, "searches": 1},
            {"year": 2026, "month": 8, "searches": 2},
        ])


def test_raw_artifact_hash_and_phase1_provenance_are_validated():
    artifact = raw_artifact()
    validate_raw_market_artifact(artifact, load_market_evidence_context())
    with pytest.raises(ValidationError, match="hash mismatch"):
        raw_artifact(raw_provider_response_sha256="0" * 64)
    with pytest.raises(ValueError, match="query-bundle hash mismatch"):
        validate_raw_market_artifact(
            artifact.model_copy(update={"query_bundle_artifact_sha256": "0" * 64}),
            load_market_evidence_context(),
        )
    forged_provenance = artifact.observations[0].provenance.model_copy(
        update={"concept_refinement_sha256": "0" * 64}
    )
    forged_observation = artifact.observations[0].model_copy(
        update={"provenance": forged_provenance}
    )
    forged_artifact = artifact.model_copy(update={"observations": (forged_observation,)})
    with pytest.raises(ValueError, match="does not match persisted query lineage"):
        validate_raw_market_artifact(forged_artifact, load_market_evidence_context())


def test_provider_response_rejects_secret_fields():
    secret_json = json.dumps({"access_token": "never-store-this"})
    with pytest.raises(ValidationError, match="credential field"):
        raw_artifact(
            raw_provider_response_json=secret_json,
            raw_provider_response_sha256=hashlib.sha256(secret_json.encode()).hexdigest(),
        )


def test_google_ads_plan_is_eligible_deterministic_and_secret_free():
    context = load_market_evidence_context()
    plan = build_google_ads_plan(
        context,
        query_ids=(MONK_QUERY_ID,),
        customer_id="6249788917",
        api_version="v25",
        scope=scope(),
        requested_time_window=window(),
    )
    assert plan == build_google_ads_plan(
        context, query_ids=(MONK_QUERY_ID,), customer_id="6249788917",
        api_version="v25", scope=scope(), requested_time_window=window(),
    )
    request = plan.provider_request()
    assert request["keywords"] == ["monk strap footwear"]
    serialized = json.dumps(request).casefold()
    assert "token" not in serialized and "authorization" not in serialized
    assert GoogleAdsHistoricalMetricsTransport is not None


def test_google_ads_plan_rejects_ambiguous_query():
    context = load_market_evidence_context()
    query = next(q for bundle in context.bundles.bundles for q in bundle.queries
                 if q.query_text == "flat folder briefcase")
    with pytest.raises(ValueError, match="ambiguous or ineligible"):
        build_google_ads_plan(
            context, query_ids=(query.query_id,), customer_id="6249788917",
            api_version="v25", scope=scope(), requested_time_window=window(),
        )


def test_market_artifact_persistence_is_immutable(tmp_path):
    target = tmp_path / "raw.json"
    persist_immutable_market_artifact(target, raw_artifact())
    with pytest.raises(FileExistsError):
        persist_immutable_market_artifact(target, raw_artifact())


def test_commercial_outputs_are_not_schema_fields():
    prohibited = {
        "demand_potential_index", "concept_ranking", "unit_demand", "inventory",
        "safety_stock", "revenue", "commercial_validation",
    }
    assert prohibited.isdisjoint(RawMarketObservation.model_fields)
    with pytest.raises(ValidationError):
        RawMarketObservation(**(raw_observation().model_dump() | {"unit_demand": 100}))
