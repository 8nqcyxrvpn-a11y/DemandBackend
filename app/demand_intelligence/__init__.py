"""Provenance-safe foundations for future demand intelligence."""

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
from .query_bundles import (
    build_candidate_artifacts,
    build_reviewed_linkage_artifact,
    load_and_validate_artifacts,
    persist_immutable_artifact,
)
from .market_evidence_models import (
    EvidenceAvailability,
    MarketQueryProvenance,
    MarketScope,
    MonthlyHistoricalObservation,
    NormalizedMarketEvidenceArtifact,
    NormalizedMarketObservation,
    ProviderResponseMetadata,
    RawMarketEvidenceArtifact,
    RawMarketObservation,
    RequestedTimeWindow,
)
from .market_evidence import (
    MarketEvidenceContext,
    load_market_evidence_context,
    normalize_raw_observation,
    persist_immutable_market_artifact,
    validate_raw_market_artifact,
)
from .google_ads_collector import (
    GoogleAdsHistoricalMetricsPlan,
    GoogleAdsHistoricalMetricsTransport,
    GoogleAdsTransportResponse,
    build_google_ads_plan,
)

__all__ = [
    "ConceptQueryBundle",
    "ConceptQueryBundleArtifact",
    "ConceptSignalLinkage",
    "ConceptSignalLinkageArtifact",
    "EvidenceRole",
    "PersistedAttributeReference",
    "QueryCandidate",
    "QueryReviewState",
    "QueryReviewEvent",
    "build_candidate_artifacts",
    "build_reviewed_linkage_artifact",
    "load_and_validate_artifacts",
    "persist_immutable_artifact",
    "EvidenceAvailability",
    "MarketQueryProvenance",
    "MarketScope",
    "MonthlyHistoricalObservation",
    "NormalizedMarketEvidenceArtifact",
    "NormalizedMarketObservation",
    "ProviderResponseMetadata",
    "RawMarketEvidenceArtifact",
    "RawMarketObservation",
    "RequestedTimeWindow",
    "MarketEvidenceContext",
    "load_market_evidence_context",
    "normalize_raw_observation",
    "persist_immutable_market_artifact",
    "validate_raw_market_artifact",
    "GoogleAdsHistoricalMetricsPlan",
    "GoogleAdsHistoricalMetricsTransport",
    "GoogleAdsTransportResponse",
    "build_google_ads_plan",
]
