"""Provenance-first contracts for factual market observations and derived trends."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import Field, HttpUrl, field_validator, model_validator

from app.brand_intelligence.enums import EvidenceStatus
from app.brand_intelligence.models import DomainModel, _require_aware


class MarketSignalType(str, Enum):
    COLOR = "color"
    MATERIAL = "material"
    SILHOUETTE_FORM = "silhouette_form"
    PRODUCT_CATEGORY = "product_category"
    CRAFTSMANSHIP_CONSTRUCTION = "craftsmanship_construction"
    AESTHETIC = "aesthetic"
    CONSUMER_BEHAVIOR = "consumer_behavior"
    SEARCH_INTEREST = "search_interest"


class MappingStatus(str, Enum):
    EXACT = "exact"
    REVIEWED = "reviewed"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class TrendMetricStatus(str, Enum):
    SUFFICIENT = "sufficient"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class MarketSource(DomainModel):
    source_id: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    is_official: bool
    source_url: Optional[HttpUrl] = None
    dataset_identifier: Optional[str] = None
    access_method: str = Field(min_length=1)
    methodology_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def requires_locator(self) -> "MarketSource":
        if not self.source_url and not self.dataset_identifier:
            raise ValueError("market source requires a URL or dataset identifier")
        return self


class MarketObservation(DomainModel):
    """Immutable factual measurement; it may not contain a derived conclusion."""

    record_kind: Literal["factual_market_observation"] = "factual_market_observation"
    observation_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_url: Optional[HttpUrl] = None
    dataset_identifier: Optional[str] = None
    retrieved_at: datetime
    period_start: datetime
    period_end: datetime
    geography: str = Field(min_length=1)
    signal_type: MarketSignalType
    raw_signal: str = Field(min_length=1)
    raw_observed_value: Any
    normalized_value: Optional[float] = None
    unit_definition: str = Field(min_length=1)
    observation_count: Optional[int] = Field(default=None, ge=1)
    source_quality: Optional[float] = Field(default=None, ge=0, le=1)
    methodology_version: str = Field(min_length=1)
    verification_status: EvidenceStatus = EvidenceStatus.PENDING
    is_fixture: bool = False
    is_synthetic: bool = False

    _retrieved_at_aware = field_validator("retrieved_at")(_require_aware)
    _period_start_aware = field_validator("period_start")(_require_aware)
    _period_end_aware = field_validator("period_end")(_require_aware)

    @field_validator("raw_observed_value")
    @classmethod
    def reject_derived_payload(cls, value: Any) -> Any:
        if isinstance(value, dict) and str(value.get("record_kind", "")).startswith("derived_"):
            raise ValueError("derived output cannot be stored as factual market evidence")
        return value

    @model_validator(mode="after")
    def validate_factual_record(self) -> "MarketObservation":
        if self.period_end < self.period_start:
            raise ValueError("period_end cannot precede period_start")
        if not self.source_url and not self.dataset_identifier:
            raise ValueError("observation requires a source URL or dataset identifier")
        if self.is_fixture and self.is_synthetic:
            raise ValueError("fixture and synthetic are distinct classifications")
        return self


class NormalizedMarketSignal(DomainModel):
    """Taxonomy mapping only; no momentum or trend claim is stored here."""

    record_kind: Literal["normalized_market_signal"] = "normalized_market_signal"
    normalized_signal_id: str = Field(min_length=1)
    observation_id: str = Field(min_length=1)
    signal_type: MarketSignalType
    raw_signal: str = Field(min_length=1)
    canonical_code: Optional[str] = None
    taxonomy_version: str = Field(min_length=1)
    mapping_status: MappingStatus
    mapping_rule_id: Optional[str] = None
    reviewed_by: Optional[str] = None

    @model_validator(mode="after")
    def mapping_state_is_consistent(self) -> "NormalizedMarketSignal":
        resolved = self.mapping_status in {MappingStatus.EXACT, MappingStatus.REVIEWED}
        if resolved and (not self.canonical_code or not self.mapping_rule_id):
            raise ValueError("resolved mappings require canonical code and mapping rule")
        if not resolved and self.canonical_code is not None:
            raise ValueError("ambiguous or unresolved mappings cannot assert a canonical code")
        if self.mapping_status == MappingStatus.REVIEWED and not self.reviewed_by:
            raise ValueError("reviewed mappings require reviewer identity")
        return self


class TrendMetrics(DomainModel):
    """Derived temporal measurements linked only to factual observation IDs."""

    record_kind: Literal["derived_trend_metrics"] = "derived_trend_metrics"
    metric_id: str = Field(min_length=1)
    canonical_code: str = Field(min_length=1)
    signal_type: MarketSignalType
    observation_ids: list[str] = Field(min_length=1)
    current_level: Optional[float] = None
    historical_baseline: Optional[float] = None
    growth_pct: Optional[float] = None
    acceleration: Optional[float] = None
    persistence_periods: int = Field(ge=0)
    geographic_breadth: int = Field(ge=0)
    source_breadth: int = Field(ge=0)
    status: TrendMetricStatus
    methodology_version: str = Field(min_length=1)
    calculated_at: datetime
    limitations: list[str] = Field(default_factory=list)
    is_live_data: bool

    _calculated_at_aware = field_validator("calculated_at")(_require_aware)


class MarketEvidenceBatch(DomainModel):
    batch_id: str = Field(min_length=1)
    batch_version: str = Field(min_length=1)
    created_at: datetime
    sources: list[MarketSource] = Field(min_length=1)
    observations: list[MarketObservation] = Field(min_length=1)
    normalized_signals: list[NormalizedMarketSignal] = Field(default_factory=list)
    derived_metrics: list[TrendMetrics] = Field(default_factory=list)

    _created_at_aware = field_validator("created_at")(_require_aware)

    @model_validator(mode="after")
    def validate_provenance(self) -> "MarketEvidenceBatch":
        sources = {item.source_id: item for item in self.sources}
        if len(sources) != len(self.sources):
            raise ValueError("duplicate market source ID")
        observations = {item.observation_id: item for item in self.observations}
        if len(observations) != len(self.observations):
            raise ValueError("duplicate market observation ID")
        natural_keys: set[tuple[Any, ...]] = set()
        for item in self.observations:
            if item.source_id not in sources:
                raise ValueError(f"unknown source ID for observation {item.observation_id}")
            source = sources[item.source_id]
            if item.dataset_identifier and source.dataset_identifier != item.dataset_identifier:
                raise ValueError(f"dataset identifier mismatch for {item.observation_id}")
            if item.source_url and source.source_url and str(item.source_url) != str(source.source_url):
                raise ValueError(f"source URL mismatch for {item.observation_id}")
            key = (item.source_id, item.period_start, item.period_end, item.geography,
                   item.signal_type, item.raw_signal.casefold())
            if key in natural_keys:
                raise ValueError("duplicate factual market observation")
            natural_keys.add(key)
        for item in self.normalized_signals:
            if item.observation_id not in observations:
                raise ValueError(f"normalized signal references unknown observation {item.observation_id}")
            if item.signal_type != observations[item.observation_id].signal_type:
                raise ValueError(f"normalized signal type mismatch for {item.observation_id}")
        for metric in self.derived_metrics:
            if not set(metric.observation_ids).issubset(observations):
                raise ValueError(f"derived metric references unknown observation {metric.metric_id}")
            referenced = [observations[item_id] for item_id in metric.observation_ids]
            if metric.is_live_data and any(
                item.is_fixture or item.is_synthetic
                or item.verification_status != EvidenceStatus.VERIFIED
                for item in referenced
            ):
                raise ValueError(f"non-real evidence cannot produce live metric {metric.metric_id}")
        return self
