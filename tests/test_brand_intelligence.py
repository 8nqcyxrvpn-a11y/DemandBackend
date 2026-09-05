from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.brand_intelligence.enums import (
    AvailabilityStatus,
    CaptureMethod,
    EvidenceStatus,
    ReviewStatus,
    SourceType,
    TraitType,
)
from app.brand_intelligence.models import (
    AssortmentItem,
    BrandDNATrait,
    DerivedInterpretation,
    EvidenceRecord,
    MarketAvailability,
    SourceRecord,
)

NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)


def source_record() -> SourceRecord:
    return SourceRecord(
        source_id="source-1",
        brand_id="brand-1",
        source_url="https://example.com/product/1",
        source_type=SourceType.PRODUCT_PAGE,
        publisher="Example Brand",
        is_official=True,
        retrieved_at=NOW,
        capture_method=CaptureMethod.MANUAL,
    )


def factual_evidence(**overrides) -> EvidenceRecord:
    values = {
        "evidence_id": "evidence-1",
        "source_id": "source-1",
        "source_url": "https://example.com/product/1",
        "brand_id": "brand-1",
        "subject_type": "product",
        "subject_id": "product-1",
        "field_name": "material",
        "observed_value": "source-stated material",
        "evidence_text": "The source states the product material.",
        "retrieved_at": NOW,
    }
    values.update(overrides)
    return EvidenceRecord(**values)


def test_source_and_evidence_carry_direct_provenance():
    source = source_record()
    evidence = factual_evidence()

    assert evidence.source_id == source.source_id
    assert str(evidence.source_url) == str(source.source_url)
    assert evidence.retrieved_at == source.retrieved_at


def test_factual_evidence_rejects_derived_record_kind():
    with pytest.raises(ValidationError, match="factual_observation"):
        factual_evidence(record_kind="derived_interpretation")


def test_factual_evidence_rejects_nested_derived_payload():
    with pytest.raises(ValidationError, match="derived interpretations"):
        factual_evidence(observed_value={"record_kind": "derived_interpretation"})


def test_scoring_evidence_must_be_verified():
    with pytest.raises(ValidationError, match="must be verified"):
        factual_evidence(eligible_for_scoring=True, status=EvidenceStatus.PENDING)

    verified = factual_evidence(eligible_for_scoring=True, status=EvidenceStatus.VERIFIED)
    assert verified.eligible_for_scoring is True


def test_approved_dna_trait_requires_evidence_and_interpretation():
    with pytest.raises(ValidationError, match="supporting evidence"):
        BrandDNATrait(
            trait_id="trait-1",
            brand_id="brand-1",
            trait_type=TraitType.MATERIAL_LANGUAGE,
            canonical_trait="material-code",
            description="Reviewed description",
            status=ReviewStatus.APPROVED,
        )

    with pytest.raises(ValidationError, match="reviewed interpretation"):
        BrandDNATrait(
            trait_id="trait-1",
            brand_id="brand-1",
            trait_type=TraitType.MATERIAL_LANGUAGE,
            canonical_trait="material-code",
            description="Reviewed description",
            status=ReviewStatus.APPROVED,
            supporting_evidence_ids=["evidence-1"],
        )


def test_derived_interpretation_requires_evidence():
    with pytest.raises(ValidationError, match="at least 1 item"):
        DerivedInterpretation(
            interpretation_id="interpretation-1",
            brand_id="brand-1",
            interpretation_type="brand_dna",
            statement="A derived statement",
            supporting_evidence_ids=[],
            confidence={
                "score": 0.8,
                "evidence_strength": 0.8,
                "source_quality": 1,
                "agreement": 0.7,
                "reason": "Multiple verified records.",
            },
            method="reviewed_rule",
            calculation_version="1.0",
            created_at=NOW,
        )


def test_product_cannot_claim_global_availability():
    values = {
        "product_id": "product-1",
        "brand_id": "brand-1",
        "canonical_name": "Observed product",
        "category_code": "category-1",
        "availability_observations": [
            MarketAvailability(
                region="FR",
                status=AvailabilityStatus.AVAILABLE,
                observed_at=NOW,
                evidence_id="evidence-1",
            )
        ],
        "supporting_evidence_ids": ["evidence-1"],
        "first_observed_at": NOW,
        "last_observed_at": NOW,
    }

    with pytest.raises(ValidationError, match="unknown"):
        AssortmentItem(**values, global_availability="available")

    item = AssortmentItem(**values)
    assert item.global_availability == "unknown"


def test_provenance_timestamps_must_be_timezone_aware():
    with pytest.raises(ValidationError, match="timezone"):
        factual_evidence(retrieved_at=datetime(2026, 9, 5))


def test_unknown_fields_are_rejected():
    values = source_record().model_dump()
    values["derived_claim"] = "not allowed"
    with pytest.raises(ValidationError, match="Extra inputs"):
        SourceRecord(**values)
