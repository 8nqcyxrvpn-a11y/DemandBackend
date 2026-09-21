"""Phase-1-grounded provenance resolution and immutable evidence persistence."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from .market_evidence_models import (
    MarketQueryProvenance,
    NormalizedMarketEvidenceArtifact,
    NormalizedMarketObservation,
    RawMarketEvidenceArtifact,
    RawMarketObservation,
)
from .models import ConceptQueryBundleArtifact, ConceptSignalLinkageArtifact, QueryReviewState
from .query_bundles import (
    DRAFTS_PATH,
    REFINEMENT_PATH,
    build_reviewed_linkage_artifact,
    load_and_validate_artifacts,
)

BUNDLE_PATH = Path("data/market_evidence/concept_query_bundles/creative_refinement_v2_query_bundles_v1.json")
LINKAGE_V1_PATH = Path("data/market_evidence/concept_signal_linkages/creative_refinement_v2_signal_linkages_v1.json")
LINKAGE_V2_PATH = Path("data/market_evidence/concept_signal_linkages/creative_refinement_v2_signal_linkages_v2.json")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_bytes(value: object) -> bytes:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


@dataclass(frozen=True)
class MarketEvidenceContext:
    bundles: ConceptQueryBundleArtifact
    reviewed_linkages: ConceptSignalLinkageArtifact
    bundle_artifact_sha256: str
    linkage_artifact_sha256: str

    def provenance_for(self, query_id: str, query_text: str | None = None) -> MarketQueryProvenance:
        query_match = None
        bundle_match = None
        for bundle in self.bundles.bundles:
            for query in bundle.queries:
                if query.query_id == query_id:
                    query_match, bundle_match = query, bundle
                    break
        if query_match is None or bundle_match is None:
            raise ValueError("unknown market query ID")
        linkage = next((item for item in self.reviewed_linkages.linkages if item.query_id == query_id), None)
        if linkage is None:
            raise ValueError("query has no reviewed linkage")
        if linkage.review_state != QueryReviewState.REVIEWED or not linkage.eligible_for_market_evidence:
            raise ValueError("ambiguous or ineligible query cannot receive market evidence")
        if query_text is not None and query_text != query_match.query_text:
            raise ValueError("market query text differs from persisted reviewed query")
        return MarketQueryProvenance(
            query_id=query_match.query_id,
            query_text=query_match.query_text,
            linkage_id=linkage.linkage_id,
            bundle_id=bundle_match.bundle_id,
            concept_id=bundle_match.concept_id,
            concept_product_name=bundle_match.product_name,
            concept_category=bundle_match.category,
            concept_refinement_sha256=bundle_match.refinement_sha256,
            refinement_version=bundle_match.refinement_version,
            refinement_artifact_path=self.bundles.source_refinement_path,
            refinement_artifact_sha256=self.bundles.source_refinement_artifact_sha256,
            query_bundle_artifact_sha256=self.bundle_artifact_sha256,
            reviewed_linkage_artifact_sha256=self.linkage_artifact_sha256,
            attribute_references=query_match.provenance,
        )


def load_market_evidence_context(
    bundle_path: Path = BUNDLE_PATH,
    linkage_v1_path: Path = LINKAGE_V1_PATH,
    linkage_v2_path: Path = LINKAGE_V2_PATH,
    refinement_path: Path = REFINEMENT_PATH,
    drafts_path: Path = DRAFTS_PATH,
) -> MarketEvidenceContext:
    bundles, v1 = load_and_validate_artifacts(bundle_path, linkage_v1_path, refinement_path, drafts_path)
    v1_hash = sha256_bytes(linkage_v1_path.read_bytes())
    persisted_v2 = ConceptSignalLinkageArtifact.model_validate_json(linkage_v2_path.read_bytes())
    expected_v2 = build_reviewed_linkage_artifact(bundles, v1, v1_hash)
    if persisted_v2 != expected_v2:
        raise ValueError("reviewed linkage artifact is stale or has failed provenance validation")
    if persisted_v2.source_refinement_artifact_sha256 != bundles.source_refinement_artifact_sha256:
        raise ValueError("reviewed linkage refinement hash mismatch")
    return MarketEvidenceContext(
        bundles=bundles,
        reviewed_linkages=persisted_v2,
        bundle_artifact_sha256=sha256_bytes(bundle_path.read_bytes()),
        linkage_artifact_sha256=sha256_bytes(linkage_v2_path.read_bytes()),
    )


def validate_raw_market_artifact(
    artifact: RawMarketEvidenceArtifact, context: MarketEvidenceContext
) -> None:
    if artifact.query_bundle_artifact_sha256 != context.bundle_artifact_sha256:
        raise ValueError("raw evidence query-bundle hash mismatch")
    if artifact.reviewed_linkage_artifact_sha256 != context.linkage_artifact_sha256:
        raise ValueError("raw evidence reviewed-linkage hash mismatch")
    if artifact.refinement_artifact_sha256 != context.bundles.source_refinement_artifact_sha256:
        raise ValueError("raw evidence refinement hash mismatch")
    for observation in artifact.observations:
        expected = context.provenance_for(
            observation.provenance.query_id, observation.provenance.query_text
        )
        if observation.provenance != expected:
            raise ValueError("raw observation provenance does not match persisted query lineage")


def normalize_raw_observation(
    observation: RawMarketObservation, raw_artifact_sha256: str
) -> NormalizedMarketObservation:
    identity = {
        "raw_observation_id": observation.observation_id,
        "raw_artifact_sha256": raw_artifact_sha256,
        "normalization_version": "market-observation-normalization-v1",
    }
    normalized_id = "normalized-market-" + sha256_bytes(canonical_bytes(identity))
    return NormalizedMarketObservation(
        normalized_observation_id=normalized_id,
        raw_observation_id=observation.observation_id,
        raw_artifact_sha256=raw_artifact_sha256,
        provider=observation.provider,
        provenance=observation.provenance,
        scope=observation.scope,
        collected_at=observation.collected_at,
        requested_time_window=observation.requested_time_window,
        availability=observation.availability,
        average_monthly_searches=observation.average_monthly_searches,
        monthly_history=observation.monthly_history,
        competition_level=observation.competition_level,
        competition_index=observation.competition_index,
        low_top_of_page_bid_micros=observation.low_top_of_page_bid_micros,
        high_top_of_page_bid_micros=observation.high_top_of_page_bid_micros,
        limitations=(
            "Public attention is not sales demand or commercial validation.",
            "Provider measurements remain source-specific and are not cross-provider scores.",
        ),
    )


def persist_immutable_market_artifact(
    path: Path, artifact: RawMarketEvidenceArtifact | NormalizedMarketEvidenceArtifact
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(json.dumps(
            artifact.model_dump(mode="json"), indent=2, sort_keys=True, ensure_ascii=False
        ).encode() + b"\n")
