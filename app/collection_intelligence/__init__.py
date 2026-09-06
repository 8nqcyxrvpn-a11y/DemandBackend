"""Internal synthetic collection generation; not connected to public APIs."""

from app.collection_intelligence.models import (
    CollectionBrief,
    CollectionDiversityRules,
    CreativeQualityGates,
    CollectionQuotas,
    GeneratedCollection,
    ProductConcept,
    SyntheticTrendSignal,
)
from app.collection_intelligence.service import generate_collection

__all__ = [
    "CollectionBrief",
    "CollectionDiversityRules",
    "CreativeQualityGates",
    "CollectionQuotas",
    "GeneratedCollection",
    "ProductConcept",
    "SyntheticTrendSignal",
    "generate_collection",
]
