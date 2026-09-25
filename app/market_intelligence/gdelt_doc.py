"""Authorized GDELT DOC 2.0 editorial/media-attention adapter.

The adapter retrieves exact-phrase TimelineVolRaw data. It does not decide
whether a phrase is fashionable and never represents news coverage as demand.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

import httpx

from app.brand_intelligence.enums import EvidenceStatus
from app.market_intelligence.models import MarketObservation, MarketSignalType, MarketSource
from app.market_intelligence.normalization import TaxonomyMappingRule

ENDPOINT = "https://api.gdeltproject.org/api/v2/doc/doc"
SOURCE_URL = "https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/"
DATASET_IDENTIFIER = "gdelt-doc-2.0.timelinevolraw"
METHODOLOGY_VERSION = "gdelt-doc-timelinevolraw-exact-phrase-v1"
TIMEOUT = httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=10.0)


class GdeltProviderError(RuntimeError):
    """Sanitized GDELT failure; response bodies and request details are excluded."""

    def __init__(
        self,
        failure_code: str,
        *,
        exception_type: str | None = None,
        http_status: int | None = None,
    ) -> None:
        parts = [f"failure={failure_code}"]
        if exception_type is not None:
            parts.append(f"exception_type={exception_type}")
        if http_status is not None:
            parts.append(f"http_status={http_status}")
        super().__init__("GDELT DOC provider failure: " + ", ".join(parts))
        self.failure_code = failure_code
        self.exception_type = exception_type
        self.http_status = http_status


@dataclass(frozen=True)
class GdeltIngestionResult:
    source: MarketSource
    raw_payload: Mapping[str, Any]
    raw_response_sha256: str
    request_parameters: Mapping[str, str]
    observations: list[MarketObservation]


def gdelt_taxonomy_rules(
    approved_rules: Sequence[TaxonomyMappingRule],
) -> list[TaxonomyMappingRule]:
    """Reuse only approved aliases while preserving GDELT's distinct signal type."""
    return [
        rule.model_copy(
            update={
                "rule_id": f"gdelt:{rule.rule_id}",
                "signal_type": MarketSignalType.EDITORIAL_MEDIA_ATTENTION.value,
            }
        )
        for rule in approved_rules
    ]


class GdeltDocAdapter:
    """Retrieve global news-attention counts for one exact phrase and date window."""

    def __init__(self, *, client: Any | None = None) -> None:
        self._client = client or httpx.Client(timeout=TIMEOUT)

    @property
    def source(self) -> MarketSource:
        return MarketSource(
            source_id="gdelt-doc-2-timelinevolraw",
            source_name="GDELT DOC 2.0 Exact-Phrase News Attention",
            provider="GDELT Project",
            is_official=True,
            source_url=SOURCE_URL,
            dataset_identifier=DATASET_IDENTIFIER,
            access_method="documented_public_doc_api",
            methodology_version=METHODOLOGY_VERSION,
        )

    def retrieve(
        self,
        exact_phrase: str,
        *,
        start: datetime,
        end: datetime,
        retrieved_at: datetime | None = None,
    ) -> GdeltIngestionResult:
        phrase = " ".join(exact_phrase.split())
        if not phrase or '"' in phrase:
            raise ValueError("exact phrase must be non-empty and cannot contain quotes")
        for name, value in (("start", start), ("end", end)):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must include a timezone")
        if end <= start:
            raise ValueError("end must be after start")
        if end - start < timedelta(days=8):
            raise ValueError("GDELT window must exceed one week to ensure daily timeline points")
        if end - start > timedelta(days=366):
            raise ValueError("GDELT window cannot exceed 366 days")
        retrieved_at = retrieved_at or datetime.now(timezone.utc)
        if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
            raise ValueError("retrieved_at must include a timezone")

        parameters = {
            "query": f'"{phrase}"',
            "mode": "timelinevolraw",
            "format": "json",
            "startdatetime": start.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"),
            "enddatetime": end.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S"),
            "timelinesmooth": "0",
        }
        try:
            response = self._client.get(ENDPOINT, params=parameters)
        except httpx.ConnectTimeout as exc:
            raise GdeltProviderError(
                "connect_timeout", exception_type="ConnectTimeout"
            ) from exc
        except httpx.ReadTimeout as exc:
            raise GdeltProviderError("read_timeout", exception_type="ReadTimeout") from exc
        except httpx.TimeoutException as exc:
            raise GdeltProviderError(
                "transport_timeout", exception_type=type(exc).__name__
            ) from exc
        except httpx.ConnectError as exc:
            raise GdeltProviderError("connect_error", exception_type="ConnectError") from exc
        except httpx.TransportError as exc:
            raise GdeltProviderError(
                "transport_error", exception_type=type(exc).__name__
            ) from exc
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise GdeltProviderError(
                "http_status", exception_type="HTTPStatusError",
                http_status=response.status_code,
            ) from exc
        raw_bytes = response.content
        try:
            payload = response.json()
        except (json.JSONDecodeError, ValueError) as exc:
            raise GdeltProviderError(
                "invalid_json", exception_type=type(exc).__name__,
                http_status=response.status_code,
            ) from exc
        if not isinstance(payload, dict):
            raise GdeltProviderError(
                "invalid_envelope", http_status=response.status_code
            )

        digest = hashlib.sha256(raw_bytes).hexdigest()
        points = self._timeline_points(payload)
        observations = [
            self._to_observation(
                phrase, point, retrieved_at=retrieved_at,
                raw_response_sha256=digest, request_parameters=parameters,
            )
            for point in points
        ]
        return GdeltIngestionResult(
            source=self.source,
            raw_payload=payload,
            raw_response_sha256=digest,
            request_parameters=parameters,
            observations=observations,
        )

    @staticmethod
    def _timeline_points(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        timeline = payload.get("timeline")
        if not isinstance(timeline, list):
            raise GdeltProviderError("missing_timeline")
        if not timeline:
            return []
        series = timeline[0]
        if not isinstance(series, dict) or not isinstance(series.get("data"), list):
            raise GdeltProviderError("invalid_timeline")
        return series["data"]

    def _to_observation(
        self,
        phrase: str,
        point: Mapping[str, Any],
        *,
        retrieved_at: datetime,
        raw_response_sha256: str,
        request_parameters: Mapping[str, str],
    ) -> MarketObservation:
        try:
            period = _parse_gdelt_datetime(point["date"])
            article_count = int(point["value"])
            monitored_count = int(point["norm"])
        except (KeyError, TypeError, ValueError) as exc:
            raise GdeltProviderError("invalid_timeline_point") from exc
        if article_count < 0 or monitored_count <= 0 or article_count > monitored_count:
            raise GdeltProviderError("invalid_article_counts")
        coverage_pct = article_count / monitored_count * 100
        identity = "|".join((phrase.casefold(), period.isoformat(), raw_response_sha256))
        return MarketObservation(
            observation_id="gdelt-doc:" + hashlib.sha256(identity.encode()).hexdigest()[:24],
            source_id=self.source.source_id,
            source_url=SOURCE_URL,
            dataset_identifier=DATASET_IDENTIFIER,
            retrieved_at=retrieved_at,
            period_start=period,
            period_end=period,
            geography="Global monitored news coverage",
            signal_type=MarketSignalType.EDITORIAL_MEDIA_ATTENTION,
            raw_signal=phrase,
            raw_observed_value={
                "article_count": article_count,
                "monitored_article_count": monitored_count,
                "coverage_pct": coverage_pct,
                "provider_point": dict(point),
                "request_parameters": dict(request_parameters),
                "raw_response_sha256": raw_response_sha256,
            },
            normalized_value=coverage_pct,
            unit_definition=(
                "Percent of all news articles monitored by GDELT in the interval that "
                "matched the exact phrase; editorial attention, not consumer demand or sales."
            ),
            observation_count=article_count or None,
            source_quality=None,
            methodology_version=METHODOLOGY_VERSION,
            verification_status=EvidenceStatus.VERIFIED,
            is_fixture=False,
            is_synthetic=False,
        )


def _parse_gdelt_datetime(value: Any) -> datetime:
    if not isinstance(value, str):
        raise ValueError("date is not text")
    for pattern in ("%Y%m%dT%H%M%SZ", "%Y%m%d%H%M%S"):
        try:
            return datetime.strptime(value, pattern).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("date must include timezone")
    return parsed.astimezone(timezone.utc)
