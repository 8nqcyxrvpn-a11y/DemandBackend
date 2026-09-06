"""Brand-independent market evidence ingestion and normalization."""

from app.market_intelligence.aggregation import derive_temporal_metrics
from app.market_intelligence.models import (
    MappingStatus,
    MarketEvidenceBatch,
    MarketObservation,
    MarketSignalType,
    MarketSource,
    NormalizedMarketSignal,
    TrendMetricStatus,
    TrendMetrics,
)
from app.market_intelligence.normalization import TaxonomyMappingRule, normalize_observation

__all__ = [
    "MappingStatus",
    "MarketEvidenceBatch",
    "MarketObservation",
    "MarketSignalType",
    "MarketSource",
    "NormalizedMarketSignal",
    "TaxonomyMappingRule",
    "TrendMetricStatus",
    "TrendMetrics",
    "derive_temporal_metrics",
    "normalize_observation",
]
