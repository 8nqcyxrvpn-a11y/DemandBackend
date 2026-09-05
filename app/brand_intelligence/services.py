"""Application ports for the future brand-evidence pipeline."""

from __future__ import annotations

from typing import Iterable, Protocol

from app.brand_intelligence.models import (
    AssortmentItem,
    BrandDNATrait,
    BrandTerritoryFeature,
    DerivedInterpretation,
    EvidenceRecord,
    SourceRecord,
)
from app.brand_intelligence.fit_models import BrandFitEvaluation, TrendEvaluationInput
from app.brand_intelligence.models import BrandEvidenceDataset


class SourceCaptureService(Protocol):
    def capture(self, source: SourceRecord) -> SourceRecord: ...


class EvidenceService(Protocol):
    def record(self, evidence: EvidenceRecord) -> EvidenceRecord: ...

    def verify(self, evidence_id: str) -> EvidenceRecord: ...


class AssortmentNormalizationService(Protocol):
    def normalize(self, evidence_ids: Iterable[str]) -> list[AssortmentItem]: ...


class BrandDNAReviewService(Protocol):
    def propose(self, interpretation: DerivedInterpretation) -> DerivedInterpretation: ...

    def approve_trait(self, trait: BrandDNATrait) -> BrandDNATrait: ...


class TerritoryIndexService(Protocol):
    def build(self, brand_id: str, calculation_version: str) -> list[BrandTerritoryFeature]: ...


class BrandFitService(Protocol):
    def evaluate(
        self, trend: TrendEvaluationInput, dataset: BrandEvidenceDataset
    ) -> BrandFitEvaluation: ...
