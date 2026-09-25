"""Transparent temporal metrics over verified, normalized market observations."""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import mean

from app.brand_intelligence.enums import EvidenceStatus
from app.market_intelligence.models import (
    MappingStatus,
    MarketObservation,
    NormalizedMarketSignal,
    TrendMetrics,
    TrendMetricStatus,
    MarketSignalType,
)

METHODOLOGY_VERSION = "temporal-trend-1.0"


def derive_temporal_metrics(
    canonical_code: str,
    normalized: list[NormalizedMarketSignal],
    observations: list[MarketObservation],
    *,
    calculated_at: datetime | None = None,
) -> TrendMetrics:
    """Use chronological numeric levels; require 3 periods and 2 sources for sufficiency."""

    observation_by_id = {item.observation_id: item for item in observations}
    mapped = [
        item for item in normalized
        if item.canonical_code == canonical_code
        and item.mapping_status in {MappingStatus.EXACT, MappingStatus.REVIEWED}
    ]
    facts = sorted(
        [observation_by_id[item.observation_id] for item in mapped if item.observation_id in observation_by_id],
        key=lambda item: (item.period_end, item.source_id, item.observation_id),
    )
    if not facts:
        raise ValueError("no resolved factual observations for canonical code")
    signal_types = {item.signal_type for item in mapped}
    if len(signal_types) == 1:
        signal_type = mapped[0].signal_type
    elif signal_types == {
        MarketSignalType.SEARCH_INTEREST,
        MarketSignalType.EDITORIAL_MEDIA_ATTENTION,
    }:
        signal_type = MarketSignalType.MARKET_ATTENTION
    else:
        raise ValueError("canonical code cannot aggregate incompatible signal types")

    verified_numeric = [
        item for item in facts
        if item.verification_status == EvidenceStatus.VERIFIED and item.normalized_value is not None
    ]
    periods = sorted({item.period_end for item in verified_numeric})
    sources = {item.source_id for item in verified_numeric}
    geographies = {item.geography for item in verified_numeric}
    has_non_real = any(item.is_fixture or item.is_synthetic for item in facts)
    sufficient = len(periods) >= 3 and len(sources) >= 2 and not has_non_real
    limitations: list[str] = []
    if len(periods) < 3:
        limitations.append("At least three distinct periods are required for temporal direction.")
    if len(sources) < 2:
        limitations.append("At least two independent sources are required for source breadth.")
    if has_non_real:
        limitations.append("Fixture or synthetic observations cannot produce live sufficient evidence.")
    if signal_type == MarketSignalType.MARKET_ATTENTION:
        limitations.append(
            "Search-interest and editorial-attention levels use provider-specific scales; "
            "source breadth is corroborative and does not make their raw magnitudes equivalent."
        )

    current = baseline = growth = acceleration = None
    if verified_numeric:
        values_by_period = {
            period: mean(item.normalized_value for item in verified_numeric if item.period_end == period)
            for period in periods
        }
        ordered = [values_by_period[period] for period in periods]
        current = round(ordered[-1], 4)
        if len(ordered) >= 2:
            baseline = round(mean(ordered[:-1]), 4)
            if baseline != 0:
                growth = round((current - baseline) / abs(baseline) * 100, 4)
        if len(ordered) >= 3:
            acceleration = round((ordered[-1] - ordered[-2]) - (ordered[-2] - ordered[-3]), 4)

    return TrendMetrics(
        metric_id=f"metrics:{canonical_code}:{METHODOLOGY_VERSION}",
        canonical_code=canonical_code,
        signal_type=signal_type,
        observation_ids=[item.observation_id for item in facts],
        current_level=current,
        historical_baseline=baseline,
        growth_pct=growth,
        acceleration=acceleration,
        persistence_periods=len(periods),
        geographic_breadth=len(geographies),
        source_breadth=len(sources),
        status=TrendMetricStatus.SUFFICIENT if sufficient else TrendMetricStatus.INSUFFICIENT_EVIDENCE,
        methodology_version=METHODOLOGY_VERSION,
        calculated_at=calculated_at or datetime.now(timezone.utc),
        limitations=limitations,
        is_live_data=sufficient,
    )
