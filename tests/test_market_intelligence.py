from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.market_intelligence import (
    MappingStatus,
    MarketEvidenceBatch,
    MarketObservation,
    TaxonomyMappingRule,
    TrendMetricStatus,
    derive_temporal_metrics,
    normalize_observation,
)


NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)
SOURCE = {
    "source_id": "source-a",
    "source_name": "Official measurement source",
    "provider": "Independent Provider",
    "is_official": True,
    "source_url": "https://data.example.org/methodology",
    "dataset_identifier": "provider.dataset.table",
    "access_method": "official_api",
    "methodology_version": "source-v1",
}


def observation(identifier="obs-1", **changes):
    values = {
        "observation_id": identifier,
        "source_id": "source-a",
        "source_url": "https://data.example.org/methodology",
        "dataset_identifier": "provider.dataset.table",
        "retrieved_at": NOW,
        "period_start": NOW - timedelta(days=7),
        "period_end": NOW,
        "geography": "US",
        "signal_type": "material",
        "raw_signal": "Silk",
        "raw_observed_value": {"index": 42},
        "normalized_value": 42,
        "unit_definition": "Fixture index, 0–100",
        "observation_count": 30,
        "source_quality": 1,
        "methodology_version": "source-v1",
        "verification_status": "verified",
        "is_fixture": True,
    }
    values.update(changes)
    return MarketObservation(**values)


def rules():
    return [TaxonomyMappingRule(rule_id="rule-silk", signal_type="material",
                                source_term="silk", canonical_code="silk",
                                taxonomy_version="fashion-taxonomy-1.0")]


def test_provenance_and_real_fixture_synthetic_separation():
    item = observation()
    assert item.source_id == "source-a"
    assert item.dataset_identifier == "provider.dataset.table"
    assert item.is_fixture is True and item.is_synthetic is False
    with pytest.raises(ValidationError, match="distinct classifications"):
        observation(is_synthetic=True)
    synthetic = observation(is_fixture=False, is_synthetic=True)
    assert synthetic.is_synthetic is True and synthetic.is_fixture is False


def test_raw_facts_cannot_contain_derived_output():
    with pytest.raises(ValidationError, match="derived output"):
        observation(raw_observed_value={"record_kind": "derived_trend_metrics"})


def test_normalization_is_exact_and_deterministic():
    first = normalize_observation(observation(), rules(), taxonomy_version="fashion-taxonomy-1.0")
    second = normalize_observation(observation(), rules(), taxonomy_version="fashion-taxonomy-1.0")
    assert first == second
    assert first.mapping_status == MappingStatus.EXACT
    assert first.canonical_code == "silk"


def test_ambiguous_and_unresolved_mapping_never_assert_codes():
    ambiguous_rules = rules() + [TaxonomyMappingRule(
        rule_id="conflict", signal_type="material", source_term="Silk",
        canonical_code="synthetic_silk", taxonomy_version="fashion-taxonomy-1.0"
    )]
    ambiguous = normalize_observation(observation(), ambiguous_rules,
                                      taxonomy_version="fashion-taxonomy-1.0")
    unresolved = normalize_observation(observation(raw_signal="unknown textile"), rules(),
                                       taxonomy_version="fashion-taxonomy-1.0")
    assert ambiguous.mapping_status == MappingStatus.AMBIGUOUS and ambiguous.canonical_code is None
    assert unresolved.mapping_status == MappingStatus.UNRESOLVED and unresolved.canonical_code is None


def test_temporal_order_and_required_provenance_validation():
    with pytest.raises(ValidationError, match="cannot precede"):
        observation(period_start=NOW, period_end=NOW - timedelta(days=1))
    with pytest.raises(ValidationError):
        observation(geography="")
    with pytest.raises(ValidationError, match="timezone"):
        observation(period_start=datetime(2026, 9, 1))


def test_batch_rejects_broken_provenance_and_duplicates():
    with pytest.raises(ValidationError, match="unknown source"):
        MarketEvidenceBatch(batch_id="b", batch_version="1", created_at=NOW,
                            sources=[SOURCE], observations=[observation(source_id="missing")])
    duplicate = observation("obs-2")
    with pytest.raises(ValidationError, match="duplicate factual"):
        MarketEvidenceBatch(batch_id="b", batch_version="1", created_at=NOW,
                            sources=[SOURCE], observations=[observation(), duplicate])


def test_fixture_isolation_and_insufficient_temporal_evidence():
    fact = observation()
    normalized = normalize_observation(fact, rules(), taxonomy_version="fashion-taxonomy-1.0")
    metrics = derive_temporal_metrics("silk", [normalized], [fact], calculated_at=NOW)
    assert metrics.record_kind == "derived_trend_metrics"
    assert metrics.status == TrendMetricStatus.INSUFFICIENT_EVIDENCE
    assert metrics.is_live_data is False
    assert metrics.observation_ids == [fact.observation_id]


def test_three_period_two_source_real_metrics_are_deterministic():
    facts = [
        observation("real-1", source_id="source-a", period_start=NOW-timedelta(days=21),
                    period_end=NOW-timedelta(days=14), normalized_value=10, is_fixture=False),
        observation("real-2", source_id="source-b", period_start=NOW-timedelta(days=14),
                    period_end=NOW-timedelta(days=7), normalized_value=15, is_fixture=False),
        observation("real-3", source_id="source-a", period_start=NOW-timedelta(days=7),
                    period_end=NOW, normalized_value=25, is_fixture=False),
    ]
    mapped = [normalize_observation(item, rules(), taxonomy_version="fashion-taxonomy-1.0")
              for item in facts]
    first = derive_temporal_metrics("silk", mapped, facts, calculated_at=NOW)
    second = derive_temporal_metrics("silk", mapped, list(reversed(facts)), calculated_at=NOW)
    assert first == second
    assert first.status == TrendMetricStatus.SUFFICIENT
    assert first.current_level == 25
    assert first.historical_baseline == 12.5
    assert first.growth_pct == 100
    assert first.acceleration == 5
    assert first.source_breadth == 2


def test_market_layer_has_no_brand_dependency():
    fields = MarketObservation.model_fields
    assert "brand_id" not in fields and "brand_name" not in fields
