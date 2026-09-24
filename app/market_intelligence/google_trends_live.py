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
from app.market_intelligence.fashion_taxonomy import (
    FashionTaxonomyEntry,
    FashionTaxonomyRegistry,
    load_production_fashion_taxonomy,
)
from app.market_intelligence.google_trends_bigquery import GoogleTrendsBigQueryAdapter
from app.market_intelligence.google_trends_runtime import classify_google_trends_failure
from app.market_intelligence.models import (
    MappingStatus,
    MarketEvidenceBatch,
    MarketObservation,
    MarketSource,
    NormalizedMarketSignal,
    TrendMetricStatus,
    TrendMetrics,
)
from app.market_intelligence.normalization import TaxonomyMappingRule, normalize_observation

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
    taxonomy_version: str
    taxonomy_artifact_sha256: str
    refresh_date_requested: date
    refresh_date_used: date
    attempted_refresh_dates: list[date] = Field(min_length=1)
    source: MarketSource
    raw_observation_count: int = Field(ge=1)
    resolved_fashion_signal_count: int = Field(ge=0)
    unresolved_count: int = Field(ge=0)
    ambiguous_count: int = Field(ge=0)
    observations: list[MarketObservation] = Field(min_length=1)
    normalized_signals: list[NormalizedMarketSignal] = Field(min_length=1)
    resolved_fashion_signals: list["ResolvedFashionSignal"] = Field(default_factory=list)
    unresolved_observations: list[MarketObservation] = Field(default_factory=list)
    ambiguous_observations: list[MarketObservation] = Field(default_factory=list)
    derived_metrics: list[TrendMetrics] = Field(default_factory=list)
    evidence_sufficient_for_derived_metrics: bool
    limitations: list[str] = Field(min_length=1)


class ResolvedFashionSignal(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    observation_id: str
    source_id: str
    normalized_signal_id: str
    raw_signal: str
    canonical_code: str
    canonical_label: str
    taxonomy_category: str
    taxonomy_version: str
    taxonomy_artifact_sha256: str
    mapping_status: MappingStatus
    mapping_rule_id: str
    reviewed_by: str | None = None


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


class GoogleTrendsLiveService:
    def __init__(
        self,
        *,
        adapter_factory: Callable[[str], GoogleTrendsBigQueryAdapter] = GoogleTrendsBigQueryAdapter,
        taxonomy_rules: Sequence[TaxonomyMappingRule] | None = None,
        taxonomy_registry: FashionTaxonomyRegistry | None = None,
        clock: Callable[[], datetime] = _utc_now,
        cache_ttl_seconds: int = CACHE_TTL_SECONDS,
    ) -> None:
        self._adapter_factory = adapter_factory
        if taxonomy_rules is None:
            registry = taxonomy_registry or load_production_fashion_taxonomy()
            self._rules = registry.rules
            self._taxonomy_version = registry.taxonomy.taxonomy_version
            self._taxonomy_artifact_sha256 = registry.artifact_sha256
            self._entries_by_code = registry.entries_by_code
        else:
            self._rules = tuple(taxonomy_rules)
            versions = {rule.taxonomy_version for rule in self._rules}
            if len(versions) != 1:
                raise ValueError("injected taxonomy rules require one taxonomy version")
            self._taxonomy_version = versions.pop()
            self._taxonomy_artifact_sha256 = "injected-rules-not-production"
            self._entries_by_code = {}
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
            normalize_observation(
                item, list(self._rules), taxonomy_version=self._taxonomy_version
            )
            for item in result.observations
        ]
        observation_by_id = {item.observation_id: item for item in result.observations}
        resolved = [
            self._resolved_signal(item, observation_by_id[item.observation_id])
            for item in normalized
            if item.mapping_status in {MappingStatus.EXACT, MappingStatus.REVIEWED}
        ]
        unresolved = [
            observation_by_id[item.observation_id] for item in normalized
            if item.mapping_status == MappingStatus.UNRESOLVED
        ]
        ambiguous = [
            observation_by_id[item.observation_id] for item in normalized
            if item.mapping_status == MappingStatus.AMBIGUOUS
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
            taxonomy_version=self._taxonomy_version,
            taxonomy_artifact_sha256=self._taxonomy_artifact_sha256,
            refresh_date_requested=requested_date,
            refresh_date_used=used_date,
            attempted_refresh_dates=attempted,
            source=batch.sources[0],
            raw_observation_count=len(batch.observations),
            resolved_fashion_signal_count=len(resolved),
            unresolved_count=len(unresolved),
            ambiguous_count=len(ambiguous),
            observations=batch.observations,
            normalized_signals=batch.normalized_signals,
            resolved_fashion_signals=resolved,
            unresolved_observations=unresolved,
            ambiguous_observations=ambiguous,
            derived_metrics=batch.derived_metrics,
            evidence_sufficient_for_derived_metrics=sufficient,
            limitations=limitations,
        )

    def _resolved_signal(
        self,
        signal: NormalizedMarketSignal,
        observation: MarketObservation,
    ) -> ResolvedFashionSignal:
        if signal.canonical_code is None or signal.mapping_rule_id is None:
            raise GoogleTrendsLiveServiceError("invalid_resolved_taxonomy_signal")
        entry = self._entries_by_code.get(signal.canonical_code)
        if entry is None:
            entry = _entry_from_canonical_code(signal.canonical_code)
        return ResolvedFashionSignal(
            observation_id=observation.observation_id,
            source_id=observation.source_id,
            normalized_signal_id=signal.normalized_signal_id,
            raw_signal=signal.raw_signal,
            canonical_code=signal.canonical_code,
            canonical_label=entry.canonical_label,
            taxonomy_category=entry.category.value,
            taxonomy_version=signal.taxonomy_version,
            taxonomy_artifact_sha256=self._taxonomy_artifact_sha256,
            mapping_status=signal.mapping_status,
            mapping_rule_id=signal.mapping_rule_id,
            reviewed_by=signal.reviewed_by,
        )


def _entry_from_canonical_code(canonical_code: str) -> FashionTaxonomyEntry:
    category, _, code = canonical_code.partition(":")
    return FashionTaxonomyEntry(
        canonical_code=canonical_code,
        category=category,
        canonical_label=code.replace("_", " ").title(),
        aliases=[canonical_code],
    )


_service = GoogleTrendsLiveService()


def load_google_trends_market_evidence() -> GoogleTrendsLiveResponse:
    return _service.load()
