import json

import pytest
from pydantic import ValidationError

from app.demand_intelligence.methodology import (
    DemandPotentialMethodologySpecification,
    load_methodology_specification,
)


def test_reviewed_preimplementation_spec_is_valid_and_non_executable():
    spec, digest = load_methodology_specification()
    assert len(digest) == 64
    assert spec.methodology_id == "demand-potential-methodology-1.0.0-preimplementation.1"
    assert spec.executable is False
    assert spec.score_calculation_permitted is False
    assert {item.dimension_id: item.weight_pct for item in spec.dimensions} == {
        "search_attention": 55,
        "search_momentum": 30,
        "advertiser_activity": 15,
    }


def test_future_dimensions_are_excluded_from_v1_score():
    spec, _ = load_methodology_specification()
    assert spec.future_dimensions_in_v1_score is False
    assert set(spec.future_candidate_dimensions) == {
        "independent_trend_intelligence", "brand_relevance"
    }
    assert not ({item.dimension_id for item in spec.dimensions} & set(spec.future_candidate_dimensions))


def test_all_calibration_parameters_are_unfrozen():
    spec, _ = load_methodology_specification()
    assert len(spec.pilot_calibration_parameters) == 7
    assert all(item.status == "pilot_calibration_required" for item in spec.pilot_calibration_parameters)
    assert all(item.frozen_value is None for item in spec.pilot_calibration_parameters)


def test_missing_states_are_distinct_and_overlap_hierarchy_is_fixed():
    spec, _ = load_methodology_specification()
    assert spec.missing_data_semantics["observed_zero"] != spec.missing_data_semantics["no_data"]
    assert all("zero" in spec.missing_data_semantics[state].casefold()
               for state in ("no_data", "suppressed", "unavailable"))
    assert spec.overlap_hierarchy == (
        "provider_result_cluster", "persisted_attribute_unit", "signal_type", "concept"
    )


def test_confidence_is_separate_and_one_provider_is_not_automatic_failure():
    spec, _ = load_methodology_specification()
    assert spec.confidence_is_separate is True
    assert sum(item.weight_pct for item in spec.confidence_components) == 100
    assert "must not fail solely" in spec.single_provider_source_breadth_rule


def test_bands_are_provisional_and_cannot_be_applied():
    spec, _ = load_methodology_specification()
    assert spec.bands_calibrated is False
    assert spec.bands_may_be_applied_to_current_concepts is False


def test_weight_or_execution_tampering_fails_closed():
    spec, _ = load_methodology_specification()
    payload = spec.model_dump(mode="json")
    payload["dimensions"][0]["weight_pct"] = 50
    with pytest.raises(ValidationError, match="55/30/15"):
        DemandPotentialMethodologySpecification.model_validate(payload)
    payload = spec.model_dump(mode="json")
    payload["executable"] = True
    with pytest.raises(ValidationError):
        DemandPotentialMethodologySpecification.model_validate(payload)


def test_spec_contains_no_scores_rankings_or_market_observations():
    spec, _ = load_methodology_specification()
    payload = json.dumps(spec.model_dump(mode="json"), sort_keys=True)
    assert "concept_id" not in payload
    assert "observation_id" not in payload
    assert "demand_potential_score" not in payload
    assert "ranking_result" not in payload
