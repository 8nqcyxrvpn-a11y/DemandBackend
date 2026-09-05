"""Provenance-first models for brand identity and assortment evidence."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from app.brand_intelligence.enums import (
    AttributeType,
    AvailabilityStatus,
    CaptureMethod,
    EvidenceStatus,
    PriceType,
    ReviewStatus,
    SeasonType,
    SourceType,
    TerritoryStatus,
    TraitType,
)


class DomainModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


def _require_aware(value: Optional[datetime]) -> Optional[datetime]:
    if value is None:
        return value
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return value


class TaxonomyTerm(DomainModel):
    """A controlled term whose meaning is stable within a taxonomy version."""

    code: str = Field(min_length=1)
    label: str = Field(min_length=1)
    taxonomy_version: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)


class Category(TaxonomyTerm):
    parent_code: Optional[str] = None


class Color(TaxonomyTerm):
    family_code: Optional[str] = None


class Material(TaxonomyTerm):
    family_code: Optional[str] = None


class SilhouetteForm(TaxonomyTerm):
    pass


class CraftsmanshipConstruction(TaxonomyTerm):
    pass


class Season(DomainModel):
    season_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    season_type: SeasonType
    taxonomy_version: str = Field(min_length=1)
    year: Optional[int] = Field(default=None, ge=1900, le=2200)
    start_date: Optional[date] = None
    end_date: Optional[date] = None

    @model_validator(mode="after")
    def validate_dates(self) -> "Season":
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("season end_date cannot precede start_date")
        return self


class Collection(DomainModel):
    collection_id: str = Field(min_length=1)
    brand_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    season_id: Optional[str] = None
    supporting_evidence_ids: list[str] = Field(default_factory=list)


class Brand(DomainModel):
    brand_id: str = Field(min_length=1)
    canonical_name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    aliases: list[str] = Field(default_factory=list)
    official_domain: Optional[str] = None
    validation_case: bool = False
    affiliation_disclaimer: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    _created_at_aware = field_validator("created_at")(_require_aware)
    _updated_at_aware = field_validator("updated_at")(_require_aware)


class SourceRecord(DomainModel):
    source_id: str = Field(min_length=1)
    brand_id: str = Field(min_length=1)
    source_url: HttpUrl
    source_type: SourceType
    publisher: str = Field(min_length=1)
    is_official: bool
    page_title: Optional[str] = None
    published_at: Optional[datetime] = None
    retrieved_at: datetime
    content_hash: Optional[str] = Field(default=None, pattern=r"^[a-fA-F0-9]{64}$")
    locale: Optional[str] = None
    region: Optional[str] = None
    capture_method: CaptureMethod

    _published_at_aware = field_validator("published_at")(_require_aware)
    _retrieved_at_aware = field_validator("retrieved_at")(_require_aware)


class EvidenceRecord(DomainModel):
    """A factual observation. Interpretations are rejected by construction."""

    record_kind: Literal["factual_observation"] = "factual_observation"
    evidence_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    source_url: HttpUrl
    brand_id: str = Field(min_length=1)
    subject_type: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    field_name: str = Field(min_length=1)
    observed_value: Any
    evidence_text: str = Field(min_length=1)
    observation_date: Optional[date] = None
    retrieved_at: datetime
    status: EvidenceStatus = EvidenceStatus.PENDING
    eligible_for_scoring: bool = False

    _retrieved_at_aware = field_validator("retrieved_at")(_require_aware)

    @field_validator("observed_value")
    @classmethod
    def reject_derived_payloads(cls, value: Any) -> Any:
        if isinstance(value, dict) and value.get("record_kind") == "derived_interpretation":
            raise ValueError("derived interpretations cannot be factual evidence")
        return value

    @model_validator(mode="after")
    def scoring_requires_verification(self) -> "EvidenceRecord":
        if self.eligible_for_scoring and self.status != EvidenceStatus.VERIFIED:
            raise ValueError("evidence used for scoring must be verified")
        return self


class NormalizedAttribute(DomainModel):
    attribute_type: AttributeType
    canonical_code: str = Field(min_length=1)
    source_value: str = Field(min_length=1)
    taxonomy_version: str = Field(min_length=1)
    supporting_evidence_ids: list[str] = Field(min_length=1)


class MarketAvailability(DomainModel):
    region: str = Field(min_length=1)
    status: AvailabilityStatus
    observed_at: datetime
    evidence_id: str = Field(min_length=1)

    _observed_at_aware = field_validator("observed_at")(_require_aware)


class AssortmentItem(DomainModel):
    product_id: str = Field(min_length=1)
    brand_id: str = Field(min_length=1)
    canonical_name: str = Field(min_length=1)
    source_product_id: Optional[str] = None
    category_code: str = Field(min_length=1)
    collection_id: Optional[str] = None
    season_id: Optional[str] = None
    attributes: list[NormalizedAttribute] = Field(default_factory=list)
    availability_observations: list[MarketAvailability] = Field(min_length=1)
    global_availability: Literal["unknown"] = "unknown"
    supporting_evidence_ids: list[str] = Field(min_length=1)
    first_observed_at: datetime
    last_observed_at: datetime

    _first_observed_at_aware = field_validator("first_observed_at")(_require_aware)
    _last_observed_at_aware = field_validator("last_observed_at")(_require_aware)

    @model_validator(mode="after")
    def validate_observation_window(self) -> "AssortmentItem":
        if self.last_observed_at < self.first_observed_at:
            raise ValueError("last_observed_at cannot precede first_observed_at")
        return self


Product = AssortmentItem


class PriceObservation(DomainModel):
    price_id: str = Field(min_length=1)
    product_id: str = Field(min_length=1)
    amount: Optional[float] = Field(default=None, ge=0)
    min_amount: Optional[float] = Field(default=None, ge=0)
    max_amount: Optional[float] = Field(default=None, ge=0)
    currency: str = Field(min_length=3, max_length=3)
    market_region: str = Field(min_length=1)
    price_type: PriceType
    observed_at: datetime
    retrieved_at: datetime
    evidence_id: str = Field(min_length=1)

    _observed_at_aware = field_validator("observed_at")(_require_aware)
    _retrieved_at_aware = field_validator("retrieved_at")(_require_aware)

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        if not value.isalpha():
            raise ValueError("currency must be a three-letter code")
        return value.upper()

    @model_validator(mode="after")
    def validate_price_shape(self) -> "PriceObservation":
        if self.price_type == PriceType.RANGE:
            if self.min_amount is None or self.max_amount is None:
                raise ValueError("range prices require min_amount and max_amount")
            if self.max_amount < self.min_amount:
                raise ValueError("max_amount cannot be less than min_amount")
        elif self.amount is None:
            raise ValueError("non-range prices require amount")
        return self


class Confidence(DomainModel):
    score: float = Field(ge=0, le=1)
    evidence_strength: float = Field(ge=0, le=1)
    source_quality: float = Field(ge=0, le=1)
    agreement: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)


class DerivedInterpretation(DomainModel):
    record_kind: Literal["derived_interpretation"] = "derived_interpretation"
    interpretation_id: str = Field(min_length=1)
    brand_id: str = Field(min_length=1)
    interpretation_type: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    supporting_evidence_ids: list[str] = Field(min_length=1)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)
    confidence: Confidence
    method: str = Field(min_length=1)
    calculation_version: str = Field(min_length=1)
    review_status: ReviewStatus = ReviewStatus.CANDIDATE
    created_at: datetime

    _created_at_aware = field_validator("created_at")(_require_aware)


class BrandDNATrait(DomainModel):
    trait_id: str = Field(min_length=1)
    brand_id: str = Field(min_length=1)
    trait_type: TraitType
    canonical_trait: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: ReviewStatus = ReviewStatus.CANDIDATE
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    interpretation_id: Optional[str] = None

    @model_validator(mode="after")
    def approved_traits_require_support(self) -> "BrandDNATrait":
        if self.status == ReviewStatus.APPROVED:
            if not self.supporting_evidence_ids:
                raise ValueError("approved Brand DNA traits require supporting evidence")
            if not self.interpretation_id:
                raise ValueError("approved Brand DNA traits require a reviewed interpretation")
        return self


class BrandTerritoryFeature(DomainModel):
    record_kind: Literal["derived_territory_feature"] = "derived_territory_feature"
    territory_id: str = Field(min_length=1)
    brand_id: str = Field(min_length=1)
    attribute_type: AttributeType
    canonical_code: str = Field(min_length=1)
    product_count: int = Field(ge=0)
    season_count: int = Field(ge=0)
    evidence_count: int = Field(ge=1)
    prevalence_score: float = Field(ge=0, le=1)
    persistence_score: float = Field(ge=0, le=1)
    status: TerritoryStatus
    supporting_product_ids: list[str] = Field(default_factory=list)
    supporting_evidence_ids: list[str] = Field(min_length=1)
    calculation_version: str = Field(min_length=1)
    calculated_at: datetime

    _calculated_at_aware = field_validator("calculated_at")(_require_aware)
