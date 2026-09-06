"""Official Google Trends BigQuery adapter using Application Default Credentials."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256
from typing import Any, Callable, Optional

from app.brand_intelligence.enums import EvidenceStatus
from app.market_intelligence.models import MarketObservation, MarketSignalType, MarketSource

DATASET_IDENTIFIER = "bigquery-public-data.google_trends.top_rising_terms"
METHODOLOGY_VERSION = "google-trends-bigquery-top-rising-v1"
SOURCE_URL = "https://console.cloud.google.com/marketplace/product/bigquery-public-datasets/google-trends"
QUERY = """\
SELECT refresh_date, week, dma_id, dma_name, term, score, rank, percent_gain
FROM `bigquery-public-data.google_trends.top_rising_terms`
WHERE refresh_date = @refresh_date
ORDER BY week DESC, rank ASC, dma_id ASC
LIMIT @row_limit
"""


@dataclass(frozen=True)
class GoogleTrendsIngestionResult:
    source: MarketSource
    raw_rows: list[dict[str, Any]]
    observations: list[MarketObservation]
    query: str
    total_bytes_processed: Optional[int]
    total_bytes_billed: Optional[int]
    job_id: Optional[str]


class GoogleTrendsBigQueryAdapter:
    """Retrieve top-rising terms; never performs fashion taxonomy mapping."""

    def __init__(
        self,
        project_id: str,
        *,
        client: Any = None,
        job_config_factory: Optional[Callable[[date, int, int], Any]] = None,
        maximum_bytes_billed: int = 109_051_904,
    ) -> None:
        self.project_id = project_id
        self.maximum_bytes_billed = maximum_bytes_billed
        if client is None:
            from google.cloud import bigquery

            client = bigquery.Client(project=project_id)

            def official_config(refresh_date: date, row_limit: int, byte_cap: int) -> Any:
                return bigquery.QueryJobConfig(
                    query_parameters=[
                        bigquery.ScalarQueryParameter("refresh_date", "DATE", refresh_date),
                        bigquery.ScalarQueryParameter("row_limit", "INT64", row_limit),
                    ],
                    maximum_bytes_billed=byte_cap,
                    use_query_cache=False,
                )

            job_config_factory = official_config
        if job_config_factory is None:
            raise ValueError("an injected client requires a job_config_factory")
        self._client = client
        self._job_config_factory = job_config_factory

    @property
    def source(self) -> MarketSource:
        return MarketSource(
            source_id="google-trends-bigquery-top-rising",
            source_name="Google Trends BigQuery: Top Rising Terms",
            provider="Google",
            is_official=True,
            source_url=SOURCE_URL,
            dataset_identifier=DATASET_IDENTIFIER,
            access_method="official_bigquery_public_dataset_with_adc",
            methodology_version=METHODOLOGY_VERSION,
        )

    def retrieve(
        self, refresh_date: date, *, row_limit: int = 25,
        retrieved_at: Optional[datetime] = None,
    ) -> GoogleTrendsIngestionResult:
        if not 1 <= row_limit <= 1000:
            raise ValueError("row_limit must be between 1 and 1000")
        retrieved_at = retrieved_at or datetime.now(timezone.utc)
        if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
            raise ValueError("retrieved_at must include a timezone")
        config = self._job_config_factory(refresh_date, row_limit, self.maximum_bytes_billed)
        job = self._client.query(QUERY, job_config=config)
        raw_rows = [dict(row.items()) for row in job.result()]
        observations = [self._to_observation(row, retrieved_at) for row in raw_rows]
        return GoogleTrendsIngestionResult(
            source=self.source,
            raw_rows=raw_rows,
            observations=observations,
            query=QUERY,
            total_bytes_processed=getattr(job, "total_bytes_processed", None),
            total_bytes_billed=getattr(job, "total_bytes_billed", None),
            job_id=getattr(job, "job_id", None),
        )

    def _to_observation(self, row: dict[str, Any], retrieved_at: datetime) -> MarketObservation:
        week = row["week"]
        if isinstance(week, str):
            week = date.fromisoformat(week)
        period_start = datetime.combine(week, time.min, tzinfo=timezone.utc)
        identity = "|".join(str(row[key]) for key in (
            "refresh_date", "week", "dma_id", "term", "rank"
        ))
        observation_id = "google-trends:" + sha256(identity.encode("utf-8")).hexdigest()[:24]
        return MarketObservation(
            observation_id=observation_id,
            source_id=self.source.source_id,
            source_url=SOURCE_URL,
            dataset_identifier=DATASET_IDENTIFIER,
            retrieved_at=retrieved_at,
            period_start=period_start,
            period_end=period_start + timedelta(days=6, hours=23, minutes=59, seconds=59),
            geography=f"US DMA {row['dma_id']}: {row['dma_name']}",
            signal_type=MarketSignalType.SEARCH_INTEREST,
            raw_signal=str(row["term"]),
            raw_observed_value={
                "refresh_date": str(row["refresh_date"]),
                "week": str(row["week"]),
                "dma_id": int(row["dma_id"]),
                "dma_name": str(row["dma_name"]),
                "score": int(row["score"]),
                "rank": int(row["rank"]),
                "percent_gain": int(row["percent_gain"]),
            },
            normalized_value=float(row["score"]),
            unit_definition=(
                "Google Trends top-rising relative score from the source table; "
                "not absolute search volume and not comparable without source methodology."
            ),
            source_quality=None,
            methodology_version=METHODOLOGY_VERSION,
            verification_status=EvidenceStatus.VERIFIED,
            is_fixture=False,
            is_synthetic=False,
        )
