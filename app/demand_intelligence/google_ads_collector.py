"""No-network Google Ads request planning and future transport boundary."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import Field, model_validator

from .market_evidence import MarketEvidenceContext
from .market_evidence_models import MarketQueryProvenance, MarketScope, RequestedTimeWindow
from .models import ImmutableModel


class GoogleAdsHistoricalMetricsPlan(ImmutableModel):
    provider: str = "google_ads_keyword_planner"
    operation: str = "GenerateKeywordHistoricalMetrics"
    api_version: str = Field(pattern=r"^v[0-9]+(?:\.[0-9]+)?$")
    customer_id: str = Field(pattern=r"^[0-9]{10}$")
    scope: MarketScope
    requested_time_window: RequestedTimeWindow
    queries: tuple[MarketQueryProvenance, ...] = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def unique_queries(self) -> "GoogleAdsHistoricalMetricsPlan":
        if len({item.query_id for item in self.queries}) != len(self.queries):
            raise ValueError("Google Ads collection plan contains duplicate query IDs")
        return self

    def provider_request(self) -> dict[str, Any]:
        """Return a secret-free REST body; authentication belongs to the future transport."""
        return {
            "keywords": [item.query_text for item in self.queries],
            "geoTargetConstants": [self.scope.geography_id],
            "language": self.scope.language_id,
            "keywordPlanNetwork": self.scope.network,
        }


class GoogleAdsTransportResponse(ImmutableModel):
    http_status: int = Field(ge=100, le=599)
    request_id: str | None = None
    response_json: str = Field(min_length=2)


class GoogleAdsHistoricalMetricsTransport(Protocol):
    """Injected transport port. Implementations must use ADC and never persist tokens."""

    def generate_keyword_historical_metrics(
        self, *, api_version: str, customer_id: str, request: dict[str, Any]
    ) -> GoogleAdsTransportResponse: ...


def build_google_ads_plan(
    context: MarketEvidenceContext,
    *,
    query_ids: tuple[str, ...],
    customer_id: str,
    api_version: str,
    scope: MarketScope,
    requested_time_window: RequestedTimeWindow,
) -> GoogleAdsHistoricalMetricsPlan:
    return GoogleAdsHistoricalMetricsPlan(
        customer_id=customer_id,
        api_version=api_version,
        scope=scope,
        requested_time_window=requested_time_window,
        queries=tuple(context.provenance_for(query_id) for query_id in query_ids),
    )
