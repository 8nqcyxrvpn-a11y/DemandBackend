"""Immutable provider-neutral contracts for factual market evidence."""

from __future__ import annotations

import json
from datetime import date, datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import Field, field_validator, model_validator

from app.brand_intelligence.models import _require_aware
from app.demand_intelligence.models import ImmutableModel, PersistedAttributeReference


class EvidenceAvailability(str, Enum):
    OBSERVED = "observed"
    NO_DATA = "no_data"
    SUPPRESSED = "suppressed"
    UNAVAILABLE = "unavailable"
    PROVIDER_ERROR = "provider_error"
    PERMISSION_DENIED = "permission_denied"


class RequestedTimeWindow(ImmutableModel):
    label: str = Field(min_length=1)
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @model_validator(mode="after")
    def valid_window(self) -> "RequestedTimeWindow":
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("requested time window needs both dates or neither")
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("requested time-window end precedes start")
        return self


class MarketScope(ImmutableModel):
    geography_id: str = Field(min_length=1)
    geography_name: str = Field(min_length=1)
    geography_level: str = Field(min_length=1)
    language_id: str = Field(min_length=1)
    language_name: str = Field(min_length=1)
    network: str = Field(min_length=1)


class MarketQueryProvenance(ImmutableModel):
    query_id: str = Field(pattern=r"^query-[0-9a-f]{64}$")
    query_text: str = Field(min_length=1)
    linkage_id: str = Field(pattern=r"^linkage-[0-9a-f]{64}$")
    bundle_id: str = Field(pattern=r"^bundle-[0-9a-f]{64}$")
    concept_id: str = Field(min_length=1)
    concept_product_name: str = Field(min_length=1)
    concept_category: str = Field(min_length=1)
    concept_refinement_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    refinement_version: Literal["creative-refinement-2"] = "creative-refinement-2"
    refinement_artifact_path: str = Field(min_length=1)
    refinement_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    query_bundle_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewed_linkage_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    attribute_references: tuple[PersistedAttributeReference, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def invented_name_is_not_a_query(self) -> "MarketQueryProvenance":
        if self.concept_product_name.casefold() in self.query_text.casefold():
            raise ValueError("invented concept names cannot be market queries")
        return self


class MonthlyHistoricalObservation(ImmutableModel):
    year: int = Field(ge=2000, le=2200)
    month: int = Field(ge=1, le=12)
    searches: Optional[int] = Field(default=None, ge=0)


class ProviderResponseMetadata(ImmutableModel):
    provider_operation: str = Field(min_length=1)
    api_version: str = Field(min_length=1)
    http_status: Optional[int] = Field(default=None, ge=100, le=599)
    request_id: Optional[str] = None
    received_at: datetime
    raw_response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider_error_code: Optional[str] = None
    provider_error_status: Optional[str] = None

    _received_at_aware = field_validator("received_at")(_require_aware)


class RawMarketObservation(ImmutableModel):
    record_kind: Literal["raw_market_observation"] = "raw_market_observation"
    evidence_origin: Literal["real_external_provider"] = "real_external_provider"
    observation_id: str = Field(pattern=r"^raw-market-[0-9a-f]{64}$")
    provider: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    provenance: MarketQueryProvenance
    scope: MarketScope
    collected_at: datetime
    requested_time_window: RequestedTimeWindow
    availability: EvidenceAvailability
    provider_keyword_text: Optional[str] = None
    close_variants: tuple[str, ...] = ()
    average_monthly_searches: Optional[int] = Field(default=None, ge=0)
    monthly_history: tuple[MonthlyHistoricalObservation, ...] = ()
    competition_level: Optional[str] = None
    competition_index: Optional[int] = Field(default=None, ge=0, le=100)
    low_top_of_page_bid_micros: Optional[int] = Field(default=None, ge=0)
    high_top_of_page_bid_micros: Optional[int] = Field(default=None, ge=0)
    response_metadata: ProviderResponseMetadata
    availability_detail: Optional[str] = None

    _collected_at_aware = field_validator("collected_at")(_require_aware)

    @model_validator(mode="after")
    def availability_matches_metrics(self) -> "RawMarketObservation":
        metrics = (
            self.average_monthly_searches,
            self.competition_level,
            self.competition_index,
            self.low_top_of_page_bid_micros,
            self.high_top_of_page_bid_micros,
        )
        has_metrics = any(value is not None for value in metrics) or any(
            item.searches is not None for item in self.monthly_history
        )
        if self.availability == EvidenceAvailability.OBSERVED and not has_metrics:
            raise ValueError("observed evidence requires an explicitly returned metric")
        if self.availability != EvidenceAvailability.OBSERVED and has_metrics:
            raise ValueError("non-observed evidence cannot carry provider metrics")
        periods = [(item.year, item.month) for item in self.monthly_history]
        if len(periods) != len(set(periods)):
            raise ValueError("duplicate monthly historical periods")
        if self.availability in {
            EvidenceAvailability.PROVIDER_ERROR,
            EvidenceAvailability.PERMISSION_DENIED,
        } and not self.response_metadata.provider_error_status:
            raise ValueError("provider failures require a sanitized error status")
        return self


class RawMarketEvidenceArtifact(ImmutableModel):
    artifact_kind: Literal["raw_market_evidence"] = "raw_market_evidence"
    schema_version: Literal["1.0"] = "1.0"
    artifact_version: str = Field(min_length=1)
    run_id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]+$")
    created_at: datetime
    provider: str = Field(min_length=1)
    query_bundle_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    reviewed_linkage_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    refinement_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_provider_response_json: str = Field(min_length=2)
    raw_provider_response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observations: tuple[RawMarketObservation, ...] = Field(min_length=1)

    _created_at_aware = field_validator("created_at")(_require_aware)

    @field_validator("raw_provider_response_json")
    @classmethod
    def response_is_json_without_secrets(cls, value: str) -> str:
        parsed = json.loads(value)
        forbidden = {"authorization", "access_token", "refresh_token", "client_secret", "developer_token"}

        def inspect(item: object) -> None:
            if isinstance(item, dict):
                if any(str(key).casefold() in forbidden for key in item):
                    raise ValueError("raw provider response contains a credential field")
                for child in item.values():
                    inspect(child)
            elif isinstance(item, list):
                for child in item:
                    inspect(child)

        inspect(parsed)
        return value

    @model_validator(mode="after")
    def artifact_is_consistent(self) -> "RawMarketEvidenceArtifact":
        import hashlib

        if hashlib.sha256(self.raw_provider_response_json.encode()).hexdigest() != self.raw_provider_response_sha256:
            raise ValueError("raw provider response hash mismatch")
        if len({item.observation_id for item in self.observations}) != len(self.observations):
            raise ValueError("duplicate raw market observation IDs")
        for item in self.observations:
            if item.provider != self.provider:
                raise ValueError("observation provider does not match artifact provider")
            if item.response_metadata.raw_response_sha256 != self.raw_provider_response_sha256:
                raise ValueError("observation response hash does not match raw response")
        return self


class NormalizedMarketObservation(ImmutableModel):
    record_kind: Literal["normalized_market_observation"] = "normalized_market_observation"
    evidence_origin: Literal["real_external_provider"] = "real_external_provider"
    normalized_observation_id: str = Field(pattern=r"^normalized-market-[0-9a-f]{64}$")
    raw_observation_id: str = Field(pattern=r"^raw-market-[0-9a-f]{64}$")
    raw_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    normalization_version: Literal["market-observation-normalization-v1"] = "market-observation-normalization-v1"
    provider: str = Field(min_length=1)
    provenance: MarketQueryProvenance
    scope: MarketScope
    collected_at: datetime
    requested_time_window: RequestedTimeWindow
    availability: EvidenceAvailability
    average_monthly_searches: Optional[int] = Field(default=None, ge=0)
    monthly_history: tuple[MonthlyHistoricalObservation, ...] = ()
    competition_level: Optional[str] = None
    competition_index: Optional[int] = Field(default=None, ge=0, le=100)
    low_top_of_page_bid_micros: Optional[int] = Field(default=None, ge=0)
    high_top_of_page_bid_micros: Optional[int] = Field(default=None, ge=0)
    limitations: tuple[str, ...] = ()

    _collected_at_aware = field_validator("collected_at")(_require_aware)

    @model_validator(mode="after")
    def no_metrics_from_missing_evidence(self) -> "NormalizedMarketObservation":
        has_metrics = any(value is not None for value in (
            self.average_monthly_searches, self.competition_level, self.competition_index,
            self.low_top_of_page_bid_micros, self.high_top_of_page_bid_micros,
        )) or any(item.searches is not None for item in self.monthly_history)
        if self.availability == EvidenceAvailability.OBSERVED and not has_metrics:
            raise ValueError("observed normalized evidence requires an explicitly returned metric")
        if self.availability != EvidenceAvailability.OBSERVED and has_metrics:
            raise ValueError("missing or failed evidence cannot be normalized into numeric metrics")
        return self


class NormalizedMarketEvidenceArtifact(ImmutableModel):
    artifact_kind: Literal["normalized_market_evidence"] = "normalized_market_evidence"
    schema_version: Literal["1.0"] = "1.0"
    artifact_version: str = Field(min_length=1)
    created_at: datetime
    raw_market_evidence_artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observations: tuple[NormalizedMarketObservation, ...] = Field(min_length=1)

    _created_at_aware = field_validator("created_at")(_require_aware)
