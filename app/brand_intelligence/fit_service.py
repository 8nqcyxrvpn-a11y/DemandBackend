"""Deterministic, conservative brand-fit and whitespace scoring."""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean

from app.brand_intelligence.enums import EvidenceStatus, ReviewStatus
from app.brand_intelligence.fit_models import (
    BrandFitEvaluation,
    EvaluationConfidence,
    FitDecision,
    TrendEvaluationInput,
)
from app.brand_intelligence.models import BrandEvidenceDataset

SCORING_VERSION = "brand-fit-1.0"
MIN_TREND_STRENGTH = 0.40
MIN_BRAND_COVERAGE = 0.20
MIN_WHITESPACE_COVERAGE = 0.60


def _rounded(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 4)


def _trend_strength(data: TrendEvaluationInput) -> float:
    referenced = [x for x in data.trend_evidence if x.evidence_id in data.trend.evidence_ids]
    verified = [x for x in referenced if x.status == EvidenceStatus.VERIFIED]
    if len(verified) != len(referenced):
        return 0.0
    quality = mean(x.source_quality for x in verified)
    volume = min(1.0, sum(x.observation_count for x in verified) / 30.0)
    diversity = min(1.0, len({x.source for x in verified}) / 2.0)
    return _rounded(quality * volume * diversity)


def _brand_coverage(dataset: BrandEvidenceDataset) -> float:
    # Fifty products across three seasons is still modest, but sufficient to allow
    # a provisional whitespace score. Smaller samples remain explicitly censored.
    product_coverage = min(1.0, len(dataset.assortment) / 50.0)
    season_coverage = min(1.0, len({x.season_id for x in dataset.assortment if x.season_id}) / 3.0)
    return _rounded(product_coverage * season_coverage)


def evaluate_brand_fit(
    data: TrendEvaluationInput,
    dataset: BrandEvidenceDataset,
    *,
    evaluated_at: datetime | None = None,
) -> BrandFitEvaluation:
    """Evaluate exact controlled-code matches; no text inference is performed."""

    trend = data.trend
    matching_attributes = [
        (item, attribute)
        for item in dataset.assortment
        for attribute in item.attributes
        if attribute.attribute_type == trend.signal_type
        and attribute.canonical_code == trend.canonical_code
        and attribute.taxonomy_version == trend.taxonomy_version
    ]
    territory_ids = sorted({eid for _, attr in matching_attributes for eid in attr.supporting_evidence_ids})
    territory = _rounded(len({item.product_id for item, _ in matching_attributes}) / len(dataset.assortment)) \
        if dataset.assortment else 0.0

    matching_traits = [
        trait for trait in dataset.dna_traits
        if trait.canonical_trait == trend.canonical_code
    ]
    trait_weights = {
        ReviewStatus.APPROVED: 1.0,
        ReviewStatus.REVIEWED: 0.70,
        ReviewStatus.CANDIDATE: 0.35,
        ReviewStatus.REJECTED: 0.0,
    }
    dna_fit = max((trait_weights[x.status] for x in matching_traits), default=0.0)
    dna_ids = sorted({eid for trait in matching_traits for eid in trait.supporting_evidence_ids})
    fit_ids = sorted(set(territory_ids + dna_ids))
    brand_fit = _rounded(0.65 * dna_fit + 0.35 * territory)

    trend_strength = _trend_strength(data)
    brand_strength = _brand_coverage(dataset)
    confidence_score = _rounded(0.55 * trend_strength + 0.45 * brand_strength)
    limitations: list[str] = []
    has_fixture_evidence = any(item.is_fixture for item in data.trend_evidence)
    if has_fixture_evidence:
        limitations.append("Trend evidence is a controlled test fixture, not a real market observation.")
    if brand_strength < MIN_BRAND_COVERAGE:
        limitations.append("Brand evidence coverage is too narrow for a reliable territory conclusion.")
    if trend_strength < MIN_TREND_STRENGTH:
        limitations.append("Trend provenance, volume, quality, or source diversity is insufficient.")

    enough_for_evaluation = (
        trend_strength >= MIN_TREND_STRENGTH and brand_strength >= MIN_BRAND_COVERAGE
        and not has_fixture_evidence
    )
    if brand_strength >= MIN_WHITESPACE_COVERAGE and trend_strength >= MIN_TREND_STRENGTH:
        whitespace = _rounded(brand_fit * (1.0 - territory))
        whitespace_explanation = (
            f"Whitespace is fit × (1 − observed territory): {brand_fit:.4f} × "
            f"(1 − {territory:.4f}). Absence is used only because coverage passed the "
            f"{MIN_WHITESPACE_COVERAGE:.2f} guardrail. Evidence IDs: {fit_ids or ['none']}."
        )
    else:
        whitespace = None
        whitespace_explanation = (
            "Whitespace was not scored: limited coverage cannot distinguish an unobserved "
            "attribute from genuine brand whitespace."
        )

    if not enough_for_evaluation:
        decision = FitDecision.INSUFFICIENT_EVIDENCE
    elif brand_fit < 0.25:
        decision = FitDecision.REJECT
    elif whitespace is not None and whitespace >= 0.45 and confidence_score >= 0.65:
        decision = FitDecision.OPPORTUNITY_CANDIDATE
    else:
        decision = FitDecision.MONITOR

    fit_explanation = (
        f"Exact taxonomy matching only. DNA contribution={dna_fit:.4f} (65% weight); "
        f"observed assortment prevalence={territory:.4f} (35% weight). "
        f"Candidate traits contribute 0.35, reviewed 0.70, approved 1.00. "
        f"Brand evidence IDs: {fit_ids or ['none']}."
    )
    return BrandFitEvaluation(
        scoring_version=SCORING_VERSION,
        brand_id=dataset.brand.brand_id,
        trend_signal=trend,
        trend_evidence=data.trend_evidence,
        brand_fit_score=brand_fit,
        brand_fit_evidence_ids=fit_ids,
        brand_fit_explanation=fit_explanation,
        existing_territory_score=territory,
        existing_territory_evidence_ids=territory_ids,
        whitespace_score=whitespace,
        whitespace_explanation=whitespace_explanation,
        confidence=EvaluationConfidence(
            score=confidence_score,
            trend_evidence_strength=trend_strength,
            brand_evidence_strength=brand_strength,
            limitations=limitations,
        ),
        decision=decision,
        evaluated_at=evaluated_at or datetime.now(timezone.utc),
    )
