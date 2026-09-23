"""One-use, non-persistent runtime preflight for Google Trends BigQuery."""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.config import google_trends_bigquery_project_id, google_trends_refresh_date
from app.market_intelligence.google_trends_bigquery import (
    DATASET_IDENTIFIER,
    METHODOLOGY_VERSION,
    GoogleTrendsBigQueryAdapter,
)


class PreflightStatus(str, Enum):
    SUCCESS_ROWS = "success_rows"
    SUCCESS_ZERO_ROWS = "success_zero_rows"
    AUTHENTICATION_FAILURE = "authentication_failure"
    PERMISSION_FAILURE = "permission_failure"
    BYTE_CAP_FAILURE = "byte_cap_failure"
    PROVIDER_QUERY_FAILURE = "provider_query_failure"


class GoogleTrendsPreflightResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: PreflightStatus
    query_succeeded: bool
    evidence_available: bool
    row_count: int = Field(ge=0)
    source_id: str
    dataset_identifier: str
    methodology_version: str
    refresh_date: str
    row_limit: int = Field(default=1, ge=1, le=1)
    total_bytes_processed: Optional[int] = Field(default=None, ge=0)
    total_bytes_billed: Optional[int] = Field(default=None, ge=0)
    job_id_present: bool = False
    diagnostic_code: str


class PreflightAlreadyExecuted(RuntimeError):
    pass


def _failure_status(exc: Exception) -> tuple[PreflightStatus, str]:
    """Classify without returning provider exception text, which can contain secrets."""
    name = type(exc).__name__.casefold()
    message = str(exc).casefold()
    if any(token in name for token in (
        "defaultcredential", "refresherror", "unauthenticated", "unauthorized",
    )):
        return PreflightStatus.AUTHENTICATION_FAILURE, "adc_authentication_failed"
    if any(token in name for token in ("forbidden", "permissiondenied")):
        return PreflightStatus.PERMISSION_FAILURE, "bigquery_permission_denied"
    if ("maximum bytes billed" in message or "bytes billed limit" in message
            or "billingtierlimit" in name):
        return PreflightStatus.BYTE_CAP_FAILURE, "maximum_bytes_billed_exceeded"
    return PreflightStatus.PROVIDER_QUERY_FAILURE, "bigquery_query_failed"


class GoogleTrendsRuntimePreflight:
    """Permits one attempt only; returned rows are counted then discarded."""

    def __init__(
        self,
        *,
        adapter_factory: Callable[[str], Any] = GoogleTrendsBigQueryAdapter,
        project_id: Optional[str] = None,
        refresh_date: Optional[date] = None,
    ) -> None:
        self._adapter_factory = adapter_factory
        self._project_id = project_id
        self._refresh_date = refresh_date
        self._executed = False

    def run(self) -> GoogleTrendsPreflightResult:
        if self._executed:
            raise PreflightAlreadyExecuted("Google Trends preflight permits exactly one attempt")
        self._executed = True
        project_id = self._project_id or google_trends_bigquery_project_id()
        refresh_date = self._refresh_date or google_trends_refresh_date()
        common = {
            "source_id": "google-trends-bigquery-top-rising",
            "dataset_identifier": DATASET_IDENTIFIER,
            "methodology_version": METHODOLOGY_VERSION,
            "refresh_date": refresh_date.isoformat(),
            "row_limit": 1,
        }
        try:
            adapter = self._adapter_factory(project_id)
            result = adapter.retrieve(
                refresh_date,
                row_limit=1,
                retrieved_at=datetime.now(timezone.utc),
                retry=None,
            )
        except Exception as exc:
            status, diagnostic = _failure_status(exc)
            return GoogleTrendsPreflightResult(
                status=status,
                query_succeeded=False,
                evidence_available=False,
                row_count=0,
                diagnostic_code=diagnostic,
                **common,
            )
        row_count = len(result.raw_rows)
        return GoogleTrendsPreflightResult(
            status=(PreflightStatus.SUCCESS_ROWS if row_count else PreflightStatus.SUCCESS_ZERO_ROWS),
            query_succeeded=True,
            evidence_available=row_count > 0,
            row_count=row_count,
            total_bytes_processed=result.total_bytes_processed,
            total_bytes_billed=result.total_bytes_billed,
            job_id_present=bool(result.job_id),
            diagnostic_code="query_completed_with_rows" if row_count else "query_completed_without_rows",
            **common,
        )
