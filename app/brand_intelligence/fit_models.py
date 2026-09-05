"""Contracts for evidence-backed brand-fit and whitespace evaluation."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal, Optional

from pydantic import Field, HttpUrl, field_validator, model_validator

from app.brand_intelligence.enums import AttributeType, EvidenceStatus
from app.brand_intelligence.models import DomainModel, _require_aware


class FitDecision(str, Enum):
    REJECT = "reject"
    MONITOR = "monitor"
    OPPORTUNITY_CANDIDATE = "opportunity_candidate"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class TrendEvidenceRecord(DomainModel):
    """Market-side provenance; deliberately separate from brand evidence."""

    evidence_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    evidence_url: HttpUrl
    region: str = Field(min_length=1)
    retrieved_at: datetime
    observation_count: int = Field(ge=1)
    source_quality: float = Field(ge=0, le=1)
    status: EvidenceStatus = EvidenceStatus.PENDING
    is_fixture: bool = False

    _retrieved_at_aware = field_validator("retrieved_at")(_require_aware)


class NormalizedTrendObservation(DomainModel):
    trend_id: str = Field(min_length=1)
    trend_signal: str = Field(min_length=1)
    signal_type: AttributeType
    canonical_code: str = Field(min_length=1)
    taxonomy_version: str = Field(min_length=1)
    interest_score: float = Field(ge=0, le=100)
    growth_pct: float
    evidence_ids: list[str] = Field(min_length=1)


class TrendEvaluationInput(DomainModel):
    trend: NormalizedTrendObservation
    trend_evidence: list[TrendEvidenceRecord] = Field(min_length=1)

    @model_validator(mode="after")
    def evidence_must_resolve(self) -> "TrendEvaluationInput":
        known = {item.evidence_id for item in self.trend_evidence}
        if not set(self.trend.evidence_ids).issubset(known):
            raise ValueError("trend references unknown trend evidence IDs")
        return self


class EvaluationConfidence(DomainModel):
    score: float = Field(ge=0, le=1)
    trend_evidence_strength: float = Field(ge=0, le=1)
    brand_evidence_strength: float = Field(ge=0, le=1)
    limitations: list[str] = Field(default_factory=list)


class BrandFitEvaluation(DomainModel):
    record_kind: Literal["derived_brand_fit_evaluation"] = "derived_brand_fit_evaluation"
    scoring_version: str
    brand_id: str
    trend_signal: NormalizedTrendObservation
    trend_evidence: list[TrendEvidenceRecord]
    brand_fit_score: float = Field(ge=0, le=1)
    brand_fit_evidence_ids: list[str]
    brand_fit_explanation: str
    existing_territory_score: Optional[float] = Field(default=None, ge=0, le=1)
    existing_territory_evidence_ids: list[str]
    whitespace_score: Optional[float] = Field(default=None, ge=0, le=1)
    whitespace_explanation: str
    confidence: EvaluationConfidence
    decision: FitDecision
    evaluated_at: datetime

    _evaluated_at_aware = field_validator("evaluated_at")(_require_aware)
