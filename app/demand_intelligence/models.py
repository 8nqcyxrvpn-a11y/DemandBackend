"""Immutable contracts for concept-to-market query preparation."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.brand_intelligence.models import DomainModel, _require_aware
from app.market_intelligence.models import MarketSignalType


class ImmutableModel(DomainModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, frozen=True)


class QueryReviewState(str, Enum):
    CANDIDATE = "candidate"
    REVIEWED = "reviewed"
    AMBIGUOUS = "ambiguous"
    REJECTED = "rejected"


class EvidenceRole(str, Enum):
    BASELINE_CATEGORY = "baseline_category"
    CONCEPT_ATTRIBUTE = "concept_attribute"


class QueryReviewEvent(ImmutableModel):
    review_version: str = Field(min_length=1)
    reviewed_at: datetime
    reviewer: str = Field(min_length=1)
    previous_state: QueryReviewState
    decision: QueryReviewState
    rationale: str = Field(min_length=1)

    _reviewed_at_aware = field_validator("reviewed_at")(_require_aware)


class PersistedAttributeReference(ImmutableModel):
    artifact_path: str = Field(min_length=1)
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    json_pointer: str = Field(pattern=r"^/")
    attribute_value: str = Field(min_length=1)
    attribute_value_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    refinement_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class QueryCandidate(ImmutableModel):
    query_id: str = Field(pattern=r"^query-[0-9a-f]{64}$")
    query_text: str = Field(min_length=1)
    signal_type: MarketSignalType
    derivation_rule_id: str = Field(min_length=1)
    derivation_rule_version: str = Field(min_length=1)
    provenance: tuple[PersistedAttributeReference, ...] = Field(min_length=1)


class ConceptQueryBundle(ImmutableModel):
    bundle_id: str = Field(pattern=r"^bundle-[0-9a-f]{64}$")
    bundle_version: Literal["concept-query-bundle-v1"] = "concept-query-bundle-v1"
    concept_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    refinement_version: Literal["creative-refinement-2"] = "creative-refinement-2"
    refinement_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    queries: tuple[QueryCandidate, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def exclude_invented_name_queries(self) -> "ConceptQueryBundle":
        name = self.product_name.casefold()
        if any(name in query.query_text.casefold() for query in self.queries):
            raise ValueError("invented concept names cannot be market queries")
        if len({query.query_id for query in self.queries}) != len(self.queries):
            raise ValueError("query IDs must be unique within a bundle")
        return self


class ConceptSignalLinkage(ImmutableModel):
    linkage_id: str = Field(pattern=r"^linkage-[0-9a-f]{64}$")
    concept_id: str = Field(min_length=1)
    bundle_id: str = Field(pattern=r"^bundle-[0-9a-f]{64}$")
    query_id: str = Field(pattern=r"^query-[0-9a-f]{64}$")
    review_state: QueryReviewState
    eligible_for_market_evidence: bool = False
    canonical_taxonomy_code: Optional[str] = None
    review_basis: Optional[str] = None
    evidence_role: EvidenceRole = EvidenceRole.CONCEPT_ATTRIBUTE
    demand_contribution_assessed: bool = False
    review_history: tuple[QueryReviewEvent, ...] = ()

    @model_validator(mode="after")
    def review_controls_eligibility(self) -> "ConceptSignalLinkage":
        if self.eligible_for_market_evidence != (self.review_state == QueryReviewState.REVIEWED):
            raise ValueError("only reviewed query mappings are eligible for market evidence")
        if self.review_state == QueryReviewState.REVIEWED:
            if not self.canonical_taxonomy_code or not self.review_basis:
                raise ValueError("reviewed mappings require taxonomy code and review basis")
        elif self.canonical_taxonomy_code is not None:
            raise ValueError("unreviewed mappings cannot assert a taxonomy code")
        if self.demand_contribution_assessed:
            raise ValueError("query review cannot assert Demand Potential contribution")
        return self


class ConceptQueryBundleArtifact(ImmutableModel):
    artifact_kind: Literal["concept_query_bundles"] = "concept_query_bundles"
    schema_version: Literal["1.0"] = "1.0"
    artifact_version: Literal["creative-refinement-v2-candidates-v1"] = "creative-refinement-v2-candidates-v1"
    created_at: datetime
    source_refinement_path: str
    source_refinement_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_refinement_version: Literal["creative-refinement-2"] = "creative-refinement-2"
    source_drafts_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    bundles: tuple[ConceptQueryBundle, ...] = Field(min_length=1)

    _created_at_aware = field_validator("created_at")(_require_aware)


class ConceptSignalLinkageArtifact(ImmutableModel):
    artifact_kind: Literal["concept_signal_linkages"] = "concept_signal_linkages"
    schema_version: Literal["1.0"] = "1.0"
    artifact_version: Literal[
        "creative-refinement-v2-linkages-v1",
        "creative-refinement-v2-linkages-v2",
    ] = "creative-refinement-v2-linkages-v1"
    created_at: datetime
    source_query_bundle_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_refinement_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    previous_linkage_artifact_sha256: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    linkages: tuple[ConceptSignalLinkage, ...] = Field(min_length=1)

    _created_at_aware = field_validator("created_at")(_require_aware)
