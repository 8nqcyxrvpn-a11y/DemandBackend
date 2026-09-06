"""Contracts for a ranked multi-option synthetic seasonal collection."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CollectionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)


class SyntheticTrendSignal(CollectionModel):
    signal_id: str = Field(min_length=1)
    signal: str = Field(min_length=1)
    signal_type: str = Field(min_length=1)
    trend_score: float = Field(ge=0, le=100)
    is_synthetic: Literal[True] = True
    data_source: Literal["synthetic_demo"] = "synthetic_demo"


class ProductConcept(CollectionModel):
    concept_id: str = Field(min_length=1)
    product_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    core_idea: str = Field(min_length=1)
    innovation: str = Field(min_length=1)
    whitespace_rationale: str = Field(min_length=1)
    materials: list[str] = Field(min_length=1)
    colors: list[str] = Field(min_length=1)
    silhouette_form: str = Field(min_length=1)
    construction_idea: str = Field(min_length=1)
    primary_trend: str = Field(min_length=1)
    trend_signal_id: str = Field(min_length=1)
    trend_score: float = Field(ge=0, le=100)
    originality_score: float = Field(ge=0, le=100)
    brand_fit_score: float = Field(ge=0, le=100)
    brand_coherence_score: float = Field(ge=0, le=100)
    commercial_potential_score: float = Field(ge=0, le=100)
    silhouette_distinctiveness_score: float = Field(ge=0, le=100)
    construction_novelty_score: float = Field(ge=0, le=100)
    shape_recognizability_score: float = Field(ge=0, le=100)
    manufacturability_score: float = Field(ge=0, le=100)
    generic_mass_market_risk: float = Field(ge=0, le=100)
    iconic_product_resemblance_risk: float = Field(ge=0, le=100)
    gimmick_weak_use_case_risk: float = Field(ge=0, le=100)
    visual_prompt_dependence_risk: float = Field(ge=0, le=100)
    product_behavior: str = Field(min_length=1)
    conceptual_mechanisms: list[Literal[
        "transformable_modular", "folding", "expansion_volume_release", "asymmetry_led"
    ]] = Field(default_factory=list)
    construction_led: bool
    base_creative_score: float | None = Field(default=None, ge=0, le=100)
    total_penalty: float | None = Field(default=None, ge=0, le=55)
    overall_opportunity_score: float | None = Field(default=None, ge=0, le=100)
    image_prompt: str = Field(min_length=1)
    is_synthetic: Literal[True] = True
    data_source: Literal["synthetic_demo"] = "synthetic_demo"

    @field_validator("materials", "colors")
    @classmethod
    def unique_values(cls, values: list[str]) -> list[str]:
        normalized = [value.casefold() for value in values]
        if len(normalized) != len(set(normalized)):
            raise ValueError("concept attributes must not contain duplicates")
        return values

    @field_validator("conceptual_mechanisms")
    @classmethod
    def unique_mechanisms(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("conceptual mechanisms must be unique")
        return values


class CollectionQuotas(CollectionModel):
    by_category: dict[str, int]

    @field_validator("by_category")
    @classmethod
    def valid_quotas(cls, quotas: dict[str, int]) -> dict[str, int]:
        if not quotas or any(not category or amount < 0 for category, amount in quotas.items()):
            raise ValueError("category quotas must be non-negative and named")
        if not 15 <= sum(quotas.values()) <= 20:
            raise ValueError("final collection quota must total between 15 and 20")
        return quotas


class CollectionDiversityRules(CollectionModel):
    maximum_primary_material_repetition: int = Field(default=6, ge=1)
    maximum_primary_color_repetition: int = Field(default=4, ge=1)
    maximum_silhouette_repetition: int = Field(default=2, ge=1)
    maximum_construction_repetition: int = Field(default=2, ge=1)
    global_semantic_similarity: float = Field(default=0.72, gt=0, le=1)
    maximum_transformable_modular: int = Field(default=3, ge=0)
    maximum_folding_based: int = Field(default=2, ge=0)
    maximum_expansion_volume_release: int = Field(default=2, ge=0)
    maximum_asymmetry_led: int = Field(default=2, ge=0)
    minimum_distinct_product_behaviors: int = Field(default=5, ge=1)
    minimum_silhouette_recognizable_concepts: int = Field(default=6, ge=1)
    minimum_construction_led_concepts: int = Field(default=4, ge=1)


class CreativeQualityGates(CollectionModel):
    minimum_silhouette_distinctiveness: float = Field(default=60, ge=0, le=100)
    minimum_construction_novelty: float = Field(default=60, ge=0, le=100)
    minimum_manufacturability: float = Field(default=55, ge=0, le=100)
    maximum_iconic_resemblance_risk: float = Field(default=69, ge=0, le=100)
    maximum_generic_mass_market_risk: float = Field(default=65, ge=0, le=100)
    maximum_gimmick_risk: float = Field(default=70, ge=0, le=100)
    maximum_visual_prompt_dependence_risk: float = Field(default=70, ge=0, le=100)
    exceptional_creative_dimension: float = Field(default=75, ge=0, le=100)


class CollectionBrief(CollectionModel):
    collection_id: str = Field(min_length=1)
    brand_label: str = Field(min_length=1)
    season: str = Field(min_length=1)
    quotas: CollectionQuotas
    diversity: CollectionDiversityRules = Field(default_factory=CollectionDiversityRules)
    quality_gates: CreativeQualityGates = Field(default_factory=CreativeQualityGates)
    score_weights: dict[str, float] = Field(default_factory=lambda: {
        "commercial_potential": 0.15,
        "originality": 0.15,
        "brand_coherence": 0.15,
        "trend_alignment": 0.10,
        "silhouette_distinctiveness": 0.15,
        "construction_novelty": 0.15,
        "shape_recognizability": 0.10,
        "manufacturability": 0.05,
    })
    is_synthetic: Literal[True] = True
    affiliation_disclaimer: str = Field(min_length=1)

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "CollectionBrief":
        required = {
            "commercial_potential", "originality", "brand_coherence", "trend_alignment",
            "silhouette_distinctiveness", "construction_novelty",
            "shape_recognizability", "manufacturability",
        }
        if set(self.score_weights) != required:
            raise ValueError("score weights must contain the eight supported components")
        if any(value < 0 for value in self.score_weights.values()):
            raise ValueError("score weights cannot be negative")
        if abs(sum(self.score_weights.values()) - 1.0) > 1e-9:
            raise ValueError("score weights must sum to 1")
        return self


class GeneratedCollection(CollectionModel):
    collection_id: str
    brand_label: str
    season: str
    concepts: list[ProductConcept] = Field(min_length=15, max_length=20)
    category_counts: dict[str, int]
    generated_at: datetime
    methodology_version: str
    is_synthetic: Literal[True] = True
    data_source: Literal["synthetic_demo"] = "synthetic_demo"
    affiliation_disclaimer: str
    limitations: list[str] = Field(min_length=1)
    rejected_candidates: dict[str, list[str]] = Field(default_factory=dict)
    diversity_audit: dict[str, int]
