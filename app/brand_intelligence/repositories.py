"""Storage ports for brand-intelligence evidence and derived records."""

from __future__ import annotations

from typing import Iterable, Optional, Protocol

from app.brand_intelligence.models import (
    AssortmentItem,
    Brand,
    BrandDNATrait,
    BrandTerritoryFeature,
    DerivedInterpretation,
    EvidenceRecord,
    SourceRecord,
)


class BrandEvidenceRepository(Protocol):
    def save_brand(self, brand: Brand) -> None: ...

    def save_source(self, source: SourceRecord) -> None: ...

    def get_source(self, source_id: str) -> Optional[SourceRecord]: ...

    def save_evidence(self, evidence: EvidenceRecord) -> None: ...

    def get_evidence(self, evidence_id: str) -> Optional[EvidenceRecord]: ...

    def get_evidence_many(self, evidence_ids: Iterable[str]) -> list[EvidenceRecord]: ...

    def save_assortment_item(self, item: AssortmentItem) -> None: ...

    def save_interpretation(self, interpretation: DerivedInterpretation) -> None: ...

    def save_dna_trait(self, trait: BrandDNATrait) -> None: ...

    def save_territory_feature(self, feature: BrandTerritoryFeature) -> None: ...

