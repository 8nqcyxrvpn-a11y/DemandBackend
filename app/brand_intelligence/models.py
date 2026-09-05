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


class BrandEvidenceDataset(DomainModel):
    """Portable, provenance-checked snapshot for a brand evidence sample."""

    dataset_id: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    created_at: datetime
    brand: Brand
    sources: list[SourceRecord] = Field(min_length=1)
    evidence: list[EvidenceRecord] = Field(min_length=1)
    categories: list[Category] = Field(default_factory=list)
    colors: list[Color] = Field(default_factory=list)
    materials: list[Material] = Field(default_factory=list)
    silhouettes: list[SilhouetteForm] = Field(default_factory=list)
    craftsmanship: list[CraftsmanshipConstruction] = Field(default_factory=list)
    seasons: list[Season] = Field(default_factory=list)
    collections: list[Collection] = Field(default_factory=list)
    assortment: list[AssortmentItem] = Field(default_factory=list)
    prices: list[PriceObservation] = Field(default_factory=list)
    interpretations: list[DerivedInterpretation] = Field(default_factory=list)
    dna_traits: list[BrandDNATrait] = Field(default_factory=list)
    territory: list[BrandTerritoryFeature] = Field(default_factory=list)

    _created_at_aware = field_validator("created_at")(_require_aware)

    @model_validator(mode="after")
    def validate_provenance_graph(self) -> "BrandEvidenceDataset":
        def unique(values: list[str], label: str) -> set[str]:
            found = set(values)
            if len(found) != len(values):
                raise ValueError(f"duplicate {label} IDs")
            return found

        source_ids = unique([x.source_id for x in self.sources], "source")
        evidence_ids = unique([x.evidence_id for x in self.evidence], "evidence")
        product_ids = unique([x.product_id for x in self.assortment], "product")
        interpretation_ids = unique(
            [x.interpretation_id for x in self.interpretations], "interpretation"
        )
        source_by_id = {x.source_id: x for x in self.sources}
        category_codes = unique([x.code for x in self.categories], "category taxonomy")
        taxonomy_codes = {
            AttributeType.COLOR: unique([x.code for x in self.colors], "color taxonomy"),
            AttributeType.MATERIAL: unique([x.code for x in self.materials], "material taxonomy"),
            AttributeType.SILHOUETTE_FORM: unique([x.code for x in self.silhouettes], "silhouette taxonomy"),
            AttributeType.CRAFTSMANSHIP_CONSTRUCTION: unique(
                [x.code for x in self.craftsmanship], "craftsmanship taxonomy"
            ),
        }
        season_ids = unique([x.season_id for x in self.seasons], "season")
        collection_ids = unique([x.collection_id for x in self.collections], "collection")

        for source in self.sources:
            if source.brand_id != self.brand.brand_id:
                raise ValueError("source brand_id does not match dataset brand")
        for fact in self.evidence:
            if fact.source_id not in source_ids:
                raise ValueError(f"unknown source_id: {fact.source_id}")
            if str(fact.source_url) != str(source_by_id[fact.source_id].source_url):
                raise ValueError(f"source URL mismatch for evidence: {fact.evidence_id}")
            if fact.brand_id != self.brand.brand_id:
                raise ValueError("evidence brand_id does not match dataset brand")
        for collection in self.collections:
            if not set(collection.supporting_evidence_ids).issubset(evidence_ids):
                raise ValueError(f"collection has unknown evidence ID: {collection.collection_id}")
            if collection.season_id and collection.season_id not in season_ids:
                raise ValueError(f"collection has unknown season ID: {collection.collection_id}")
        for item in self.assortment:
            refs = item.supporting_evidence_ids + [
                ref
                for attr in item.attributes
                for ref in attr.supporting_evidence_ids
            ] + [x.evidence_id for x in item.availability_observations]
            if not set(refs).issubset(evidence_ids):
                raise ValueError(f"product has unknown evidence ID: {item.product_id}")
            if item.category_code not in category_codes:
                raise ValueError(f"product has unknown category code: {item.product_id}")
            if item.collection_id and item.collection_id not in collection_ids:
                raise ValueError(f"product has unknown collection ID: {item.product_id}")
            if item.season_id and item.season_id not in season_ids:
                raise ValueError(f"product has unknown season ID: {item.product_id}")
            for attribute in item.attributes:
                if attribute.canonical_code not in taxonomy_codes[attribute.attribute_type]:
                    raise ValueError(f"product has unknown taxonomy code: {item.product_id}")
        for price in self.prices:
            if price.product_id not in product_ids or price.evidence_id not in evidence_ids:
                raise ValueError(f"price provenance is incomplete: {price.price_id}")
        for interpretation in self.interpretations:
            refs = interpretation.supporting_evidence_ids + interpretation.contradicting_evidence_ids
            if not set(refs).issubset(evidence_ids):
                raise ValueError(
                    f"interpretation has unknown evidence ID: {interpretation.interpretation_id}"
                )
        for trait in self.dna_traits:
            if not set(trait.supporting_evidence_ids).issubset(evidence_ids):
                raise ValueError(f"trait has unknown evidence ID: {trait.trait_id}")
            if trait.interpretation_id and trait.interpretation_id not in interpretation_ids:
                raise ValueError(f"trait has unknown interpretation ID: {trait.trait_id}")
        return self
