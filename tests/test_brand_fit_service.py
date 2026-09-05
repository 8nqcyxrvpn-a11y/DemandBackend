from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.brand_intelligence.datasets import load_evidence_dataset
from app.brand_intelligence.enums import EvidenceStatus, ReviewStatus
from app.brand_intelligence.fit_models import FitDecision, TrendEvaluationInput
from app.brand_intelligence.fit_service import evaluate_brand_fit
from app.brand_intelligence.models import BrandEvidenceDataset


NOW = datetime(2026, 9, 5, 16, 0, tzinfo=timezone.utc)
DATASET_PATH = Path(__file__).parents[1] / "data/brand_evidence/hermes/validation_v1.json"


def dataset() -> BrandEvidenceDataset:
    return load_evidence_dataset(DATASET_PATH)


def trend_input(
    *,
    canonical_code="silk",
    status=EvidenceStatus.VERIFIED,
    evidence_ids=None,
) -> TrendEvaluationInput:
    ids = evidence_ids or ["trend-ev-1", "trend-ev-2"]
    return TrendEvaluationInput(
        trend={
            "trend_id": "fixture-trend-1",
            "trend_signal": "Fixture silk signal",
            "signal_type": "material",
            "canonical_code": canonical_code,
            "taxonomy_version": "fashion-taxonomy-1.0",
            "interest_score": 70,
            "growth_pct": 20,
            "evidence_ids": ids,
        },
        trend_evidence=[
            {
                "evidence_id": "trend-ev-1",
                "source": "fixture-source-a",
                "evidence_url": "https://fixtures.invalid/a",
                "region": "US",
                "retrieved_at": NOW,
                "observation_count": 15,
                "source_quality": 1,
                "status": status,
                "is_fixture": True,
            },
            {
                "evidence_id": "trend-ev-2",
                "source": "fixture-source-b",
                "evidence_url": "https://fixtures.invalid/b",
                "region": "GB",
                "retrieved_at": NOW,
                "observation_count": 15,
                "source_quality": 1,
                "status": status,
                "is_fixture": True,
            },
        ],
    )


def test_provenance_is_preserved_and_layers_remain_separate():
    result = evaluate_brand_fit(trend_input(), dataset(), evaluated_at=NOW)

    assert [x.evidence_id for x in result.trend_evidence] == ["trend-ev-1", "trend-ev-2"]
    assert set(result.brand_fit_evidence_ids).issubset({f"ev-p{x:02d}" for x in range(1, 13)})
    assert not set(result.brand_fit_evidence_ids) & set(result.trend_signal.evidence_ids)
    assert "ev-p03" in result.existing_territory_evidence_ids
    assert "ev-p08" in result.existing_territory_evidence_ids


def test_scores_are_reproducible():
    first = evaluate_brand_fit(trend_input(), dataset(), evaluated_at=NOW)
    second = evaluate_brand_fit(trend_input(), dataset(), evaluated_at=NOW)

    assert first == second


def test_fixture_trends_never_progress_to_opportunity():
    result = evaluate_brand_fit(trend_input(), dataset(), evaluated_at=NOW)

    assert result.decision == FitDecision.INSUFFICIENT_EVIDENCE
    assert any("controlled test fixture" in item for item in result.confidence.limitations)


def test_missing_or_unverified_trend_evidence_is_insufficient():
    result = evaluate_brand_fit(
        trend_input(status=EvidenceStatus.PENDING), dataset(), evaluated_at=NOW
    )

    assert result.confidence.trend_evidence_strength == 0
    assert result.decision == FitDecision.INSUFFICIENT_EVIDENCE

    with pytest.raises(ValidationError, match="unknown trend evidence"):
        trend_input(evidence_ids=["missing"])


def test_candidate_traits_have_less_weight_than_approved_traits():
    candidate_data = dataset()
    candidate_data.dna_traits[0].canonical_trait = "silk"
    candidate_data.dna_traits[0].status = ReviewStatus.CANDIDATE
    approved_data = candidate_data.model_copy(deep=True)
    approved_data.dna_traits[0].status = ReviewStatus.APPROVED

    candidate = evaluate_brand_fit(trend_input(), candidate_data, evaluated_at=NOW)
    approved = evaluate_brand_fit(trend_input(), approved_data, evaluated_at=NOW)

    assert candidate.brand_fit_score < approved.brand_fit_score
    assert "Candidate traits contribute 0.35" in candidate.brand_fit_explanation


def test_small_sample_never_turns_absence_into_whitespace():
    result = evaluate_brand_fit(
        trend_input(canonical_code="material.not_observed"), dataset(), evaluated_at=NOW
    )

    assert result.existing_territory_score == 0
    assert result.whitespace_score is None
    assert result.decision == FitDecision.INSUFFICIENT_EVIDENCE
    assert "cannot distinguish" in result.whitespace_explanation


def test_engine_is_brand_agnostic():
    payload = dataset().model_dump(mode="json")
    payload["brand"]["brand_id"] = "validation-brand-b"
    payload["brand"]["canonical_name"] = "Validation Brand B"
    payload["brand"]["display_name"] = "Validation Brand B"
    for group in ("sources", "evidence", "collections", "assortment", "interpretations", "dna_traits"):
        for item in payload[group]:
            item["brand_id"] = "validation-brand-b"
    other_brand = BrandEvidenceDataset.model_validate(payload)

    result = evaluate_brand_fit(trend_input(), other_brand, evaluated_at=NOW)

    assert result.brand_id == "validation-brand-b"
    assert result.existing_territory_score == pytest.approx(2 / 12, abs=0.0001)
