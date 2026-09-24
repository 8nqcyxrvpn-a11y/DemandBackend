"""Live, provenance-preserving Google Trends market-evidence service."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from threading import Lock
from typing import Callable, Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.brand_intelligence.enums import EvidenceStatus
from app.config import google_trends_bigquery_project_id
from app.market_intelligence.aggregation import derive_temporal_metrics
from app.market_intelligence.google_trends_bigquery import GoogleTrendsBigQueryAdapter
from app.market_intelligence.google_trends_runtime import classify_google_trends_failure
from app.market_intelligence.models import (
    MarketEvidenceBatch,
    MarketObservation,
    MarketSource,
    NormalizedMarketSignal,
    TrendMetricStatus,
    TrendMetrics,
)
from app.market_intelligence.normalization import TaxonomyMappingRule, normalize_observation

TAXONOMY_VERSION = "fashion-taxonomy-1.0"
LIVE_ROW_LIMIT = 25
MAX_DATE_LOOKBACK_DAYS = 14
MAX_CONFIGURED_DATE_AGE_DAYS = 14
CACHE_TTL_SECONDS = 900


class GoogleTrendsLiveServiceError(RuntimeError):
    """Sanitized live-provider failure suitable for an API diagnostic code."""

    def __init__(self, diagnostic_code: str) -> None:
        super().__init__("Google Trends market evidence is unavailable")
        self.diagnostic_code = diagnostic_code


class GoogleTrendsLiveResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: str = "success"
    data_source: str = "google_trends_bigquery"
    is_live_data: bool = True
    batch_id: str
    batch_version: str
    refresh_date_requested: date
    refresh_date_used: date
    attempted_refresh_dates: list[date] = Field(min_length=1)
    source: MarketSource
    observations: list[MarketObservation] = Field(min_length=1)
    normalized_signals: list[NormalizedMarketSignal] = Field(min_length=1)
    derived_metrics: list[TrendMetrics] = Field(default_factory=list)
    evidence_sufficient_for_derived_metrics: bool
    limitations: list[str] = Field(min_length=1)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def select_start_date(*, today: date) -> date:
    """Prefer a recent configured date; reject malformed configuration."""
    raw = os.getenv("GOOGLE_TRENDS_REFRESH_DATE", "").strip()
    if not raw:
        return today
    try:
        configured = date.fromisoformat(raw)
    except ValueError as exc:
        raise GoogleTrendsLiveServiceError("invalid_refresh_date_configuration") from exc
    age = (today - configured).days
    return configured if 0 <= age <= MAX_CONFIGURED_DATE_AGE_DAYS else today


def approved_google_trends_taxonomy_rules() -> tuple[TaxonomyMappingRule, ...]:
    """No Google Trends terms are approved for automatic fashion mapping yet."""
    return ()


class GoogleTrendsLiveService:
    def __init__(
        self,
        *,
        adapter_factory: Callable[[str], GoogleTrendsBigQueryAdapter] = GoogleTrendsBigQueryAdapter,
        taxonomy_rules: Sequence[TaxonomyMappingRule] | None = None,
        clock: Callable[[], datetime] = _utc_now,
        cache_ttl_seconds: int = CACHE_TTL_SECONDS,
    ) -> None:
        self._adapter_factory = adapter_factory
        self._rules = tuple(
            approved_google_trends_taxonomy_rules() if taxonomy_rules is None else taxonomy_rules
        )
        self._clock = clock
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cached: GoogleTrendsLiveResponse | None = None
        self._cache_expires_at: datetime | None = None
        self._lock = Lock()

    def load(self) -> GoogleTrendsLiveResponse:
        now = self._clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise GoogleTrendsLiveServiceError("invalid_runtime_clock")
        with self._lock:
            if self._cached is not None and self._cache_expires_at is not None:
                if now < self._cache_expires_at:
                    return self._cached
            response = self._retrieve(now)
            self._cached = response
            self._cache_expires_at = now + timedelta(seconds=self._cache_ttl_seconds)
            return response

    def _retrieve(self, now: datetime) -> GoogleTrendsLiveResponse:
        try:
            project_id = google_trends_bigquery_project_id()
            requested_date = select_start_date(today=now.date())
            adapter = self._adapter_factory(project_id)
        except GoogleTrendsLiveServiceError:
            raise
        except ValueError as exc:
            raise GoogleTrendsLiveServiceError("missing_project_configuration") from exc
        except Exception as exc:
            _, diagnostic = classify_google_trends_failure(exc)
            raise GoogleTrendsLiveServiceError(diagnostic) from exc

        attempted: list[date] = []
        result = None
        used_date = requested_date
        for offset in range(MAX_DATE_LOOKBACK_DAYS + 1):
            candidate = requested_date - timedelta(days=offset)
            attempted.append(candidate)
            try:
                candidate_result = adapter.retrieve(
                    candidate,
                    row_limit=LIVE_ROW_LIMIT,
                    retrieved_at=now,
                )
            except Exception as exc:
                _, diagnostic = classify_google_trends_failure(exc)
                raise GoogleTrendsLiveServiceError(diagnostic) from exc
            if candidate_result.raw_rows:
                result = candidate_result
                used_date = candidate
                break
        if result is None:
            raise GoogleTrendsLiveServiceError("no_rows_in_bounded_date_window")
        if any(
            item.is_fixture or item.is_synthetic
            or item.verification_status != EvidenceStatus.VERIFIED
            for item in result.observations
        ):
            raise GoogleTrendsLiveServiceError("invalid_observation_classification")

        normalized = [
            normalize_observation(item, list(self._rules), taxonomy_version=TAXONOMY_VERSION)
            for item in result.observations
        ]
        canonical_codes = sorted({
            item.canonical_code for item in normalized if item.canonical_code is not None
        })
        metrics = [
            derive_temporal_metrics(code, normalized, result.observations, calculated_at=now)
            for code in canonical_codes
        ]
        sufficient = bool(metrics) and all(
            item.status == TrendMetricStatus.SUFFICIENT for item in metrics
        )
        limitations = [
            "Google Trends top-rising values are relative attention signals, not absolute search volume or sales demand.",
            "Raw terms are not fashion signals unless an explicit reviewed taxonomy rule resolves them.",
            "Google Trends is one source; it cannot satisfy the two-source breadth requirement by itself.",
        ]
        if not canonical_codes:
            limitations.append("No retrieved term matched an approved fashion taxonomy rule.")
        if metrics and not sufficient:
            limitations.append("Resolved signals do not satisfy the existing derived-metric evidence requirements.")

        batch = MarketEvidenceBatch(
            batch_id=f"google-trends-live:{used_date.isoformat()}:{now.isoformat()}",
            batch_version="google-trends-live-v1",
            created_at=now,
            sources=[result.source],
            observations=result.observations,
            normalized_signals=normalized,
            derived_metrics=metrics,
        )

        return GoogleTrendsLiveResponse(
            batch_id=batch.batch_id,
            batch_version=batch.batch_version,
            refresh_date_requested=requested_date,
            refresh_date_used=used_date,
            attempted_refresh_dates=attempted,
            source=batch.sources[0],
            observations=batch.observations,
            normalized_signals=batch.normalized_signals,
            derived_metrics=batch.derived_metrics,
            evidence_sufficient_for_derived_metrics=sufficient,
            limitations=limitations,
        )


_service = GoogleTrendsLiveService()


def load_google_trends_market_evidence() -> GoogleTrendsLiveResponse:
    return _service.load()
