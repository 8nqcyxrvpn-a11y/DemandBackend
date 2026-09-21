"""Validation for private, non-executable Demand Potential methodology specs."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from .models import ImmutableModel

METHODOLOGY_SPEC_PATH = Path(
    "data/methodologies/demand_potential/"
    "demand_potential_methodology_v1_preimplementation.json"
)


class DimensionSpecification(ImmutableModel):
    dimension_id: Literal[
        "search_attention", "search_momentum", "advertiser_activity"
    ]
    weight_pct: int = Field(ge=0, le=100)
    meaning: str = Field(min_length=1)
    permitted_inputs: tuple[str, ...] = Field(min_length=1)
    exclusions: tuple[str, ...] = Field(min_length=1)


class ConfidenceComponent(ImmutableModel):
    component_id: Literal[
        "attribute_type_coverage",
        "temporal_completeness",
        "collection_completeness",
        "scope_consistency",
        "independent_source_breadth",
        "provenance_integrity",
    ]
    weight_pct: int = Field(ge=0, le=100)
    rule: str = Field(min_length=1)


class PilotCalibrationParameter(ImmutableModel):
    parameter_id: Literal[
        "attention_percentiles",
        "category_context_adjustment",
        "provider_close_variant_allocation",
        "minimum_historical_months",
        "momentum_comparison_window",
        "bid_normalization",
        "reportability_thresholds",
    ]
    status: Literal["pilot_calibration_required"] = "pilot_calibration_required"
    conceptual_approach: str = Field(min_length=1)
    frozen_value: None = None


class ProvisionalBand(ImmutableModel):
    label: Literal["Very Low", "Low", "Moderate", "High", "Very High"]
    lower_inclusive: int = Field(ge=0, le=100)
    upper_inclusive: int = Field(ge=0, le=100)


class DemandPotentialMethodologySpecification(ImmutableModel):
    artifact_kind: Literal[
        "private_demand_potential_methodology_specification"
    ] = "private_demand_potential_methodology_specification"
    schema_version: Literal["1.0"] = "1.0"
    methodology_id: Literal[
        "demand-potential-methodology-1.0.0-preimplementation.1"
    ]
    status: Literal["reviewed_preimplementation_non_executable"]
    executable: Literal[False]
    score_calculation_permitted: Literal[False]
    definition: str = Field(min_length=1)
    prohibited_interpretations: tuple[str, ...] = Field(min_length=1)
    fixed_principles: tuple[str, ...] = Field(min_length=1)
    dimensions: tuple[DimensionSpecification, ...] = Field(min_length=3, max_length=3)
    overlap_hierarchy: tuple[
        Literal[
            "provider_result_cluster",
            "persisted_attribute_unit",
            "signal_type",
            "concept",
        ], ...
    ]
    baseline_category_treatment: str = Field(min_length=1)
    missing_data_semantics: dict[str, str]
    confidence_is_separate: Literal[True]
    confidence_components: tuple[ConfidenceComponent, ...] = Field(min_length=6, max_length=6)
    single_provider_source_breadth_rule: str = Field(min_length=1)
    pilot_calibration_parameters: tuple[PilotCalibrationParameter, ...] = Field(min_length=7, max_length=7)
    provisional_bands: tuple[ProvisionalBand, ...] = Field(min_length=5, max_length=5)
    bands_calibrated: Literal[False]
    bands_may_be_applied_to_current_concepts: Literal[False]
    future_candidate_dimensions: tuple[Literal[
        "independent_trend_intelligence", "brand_relevance"
    ], ...]
    future_dimensions_in_v1_score: Literal[False]
    provenance_requirements: tuple[str, ...] = Field(min_length=1)
    versioning_policy: tuple[str, ...] = Field(min_length=1)
    unresolved_questions: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def reviewed_design_is_exact_and_non_executable(
        self,
    ) -> "DemandPotentialMethodologySpecification":
        weights = {item.dimension_id: item.weight_pct for item in self.dimensions}
        if weights != {
            "search_attention": 55,
            "search_momentum": 30,
            "advertiser_activity": 15,
        }:
            raise ValueError("v1 dimensions must use the reviewed 55/30/15 weights")
        if sum(weights.values()) != 100:
            raise ValueError("v1 dimension weights must sum to 100")
        if self.overlap_hierarchy != (
            "provider_result_cluster",
            "persisted_attribute_unit",
            "signal_type",
            "concept",
        ):
            raise ValueError("query-overlap hierarchy does not match the reviewed design")
        required_states = {
            "observed_zero", "no_data", "suppressed", "unavailable",
            "provider_error", "permission_denied",
        }
        if set(self.missing_data_semantics) != required_states:
            raise ValueError("missing-data semantics are incomplete")
        if self.missing_data_semantics["observed_zero"] == self.missing_data_semantics["no_data"]:
            raise ValueError("observed zero and no_data must remain distinct")
        calibration_ids = {item.parameter_id for item in self.pilot_calibration_parameters}
        if calibration_ids != {
            "attention_percentiles", "category_context_adjustment",
            "provider_close_variant_allocation", "minimum_historical_months",
            "momentum_comparison_window", "bid_normalization",
            "reportability_thresholds",
        }:
            raise ValueError("pilot-calibration parameter set is incomplete")
        if sum(item.weight_pct for item in self.confidence_components) != 100:
            raise ValueError("confidence component weights must sum to 100")
        return self


def load_methodology_specification(
    path: Path = METHODOLOGY_SPEC_PATH,
) -> tuple[DemandPotentialMethodologySpecification, str]:
    raw = path.read_bytes()
    return (
        DemandPotentialMethodologySpecification.model_validate_json(raw),
        hashlib.sha256(raw).hexdigest(),
    )
