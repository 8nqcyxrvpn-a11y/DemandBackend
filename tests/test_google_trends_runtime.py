from datetime import date
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import server
from app.market_intelligence.google_trends_bigquery import GoogleTrendsBigQueryAdapter
from app.market_intelligence.google_trends_runtime import (
    GoogleTrendsRuntimePreflight,
    PreflightAlreadyExecuted,
    PreflightStatus,
)


class FakeAdapter:
    def __init__(self, project_id, *, rows=None, failure=None):
        self.project_id = project_id
        self.rows = [] if rows is None else rows
        self.failure = failure
        self.calls = []
        self.source = SimpleNamespace(
            source_id="google-trends-bigquery-top-rising",
            dataset_identifier="bigquery-public-data.google_trends.top_rising_terms",
            methodology_version="google-trends-bigquery-top-rising-v1",
        )

    def retrieve(self, refresh_date, **kwargs):
        self.calls.append((refresh_date, kwargs))
        if self.failure:
            raise self.failure
        return SimpleNamespace(
            raw_rows=self.rows,
            observations=[],
            total_bytes_processed=100,
            total_bytes_billed=100,
            job_id="fake-job",
        )


def factory_for(adapter):
    def factory(project_id):
        assert project_id == "execution-project"
        return adapter
    return factory


def test_missing_project_id_fails_closed(monkeypatch):
    monkeypatch.delenv("GOOGLE_TRENDS_BIGQUERY_PROJECT_ID", raising=False)
    with pytest.raises(ValueError, match="PROJECT_ID is required"):
        GoogleTrendsRuntimePreflight(refresh_date=date(2026, 9, 3)).run()


def test_missing_or_invalid_refresh_date_fails_closed(monkeypatch):
    monkeypatch.setenv("GOOGLE_TRENDS_BIGQUERY_PROJECT_ID", "execution-project")
    monkeypatch.delenv("GOOGLE_TRENDS_REFRESH_DATE", raising=False)
    with pytest.raises(ValueError, match="REFRESH_DATE is required"):
        GoogleTrendsRuntimePreflight(adapter_factory=lambda _: None).run()
    monkeypatch.setenv("GOOGLE_TRENDS_REFRESH_DATE", "09/03/2026")
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        GoogleTrendsRuntimePreflight(adapter_factory=lambda _: None).run()


def test_exactly_one_retrieve_with_limit_one_and_retries_disabled():
    adapter = FakeAdapter("execution-project", rows=[{"term": "real provider row"}])
    preflight = GoogleTrendsRuntimePreflight(
        adapter_factory=factory_for(adapter),
        project_id="execution-project",
        refresh_date=date(2026, 9, 3),
    )
    result = preflight.run()
    assert result.status == PreflightStatus.SUCCESS_ROWS
    assert result.row_count == 1 and result.evidence_available is True
    assert len(adapter.calls) == 1
    assert adapter.calls[0][1]["row_limit"] == 1
    assert adapter.calls[0][1]["retry"] is None
    with pytest.raises(PreflightAlreadyExecuted, match="exactly one"):
        preflight.run()
    assert len(adapter.calls) == 1


def test_zero_rows_is_success_not_failure():
    adapter = FakeAdapter("execution-project", rows=[])
    result = GoogleTrendsRuntimePreflight(
        adapter_factory=factory_for(adapter), project_id="execution-project",
        refresh_date=date(2026, 9, 3),
    ).run()
    assert result.status == PreflightStatus.SUCCESS_ZERO_ROWS
    assert result.query_succeeded is True
    assert result.evidence_available is False
    assert result.row_count == 0


class DefaultCredentialsError(Exception):
    pass


class PermissionDenied(Exception):
    pass


class BadRequest(Exception):
    pass


@pytest.mark.parametrize(("failure", "status", "diagnostic"), [
    (DefaultCredentialsError("private_key=SECRET token=SECRET"),
     PreflightStatus.AUTHENTICATION_FAILURE, "adc_authentication_failed"),
    (PermissionDenied("Authorization: Bearer SECRET"),
     PreflightStatus.PERMISSION_FAILURE, "bigquery_permission_denied"),
    (BadRequest("Query exceeded maximum bytes billed; credential=SECRET"),
     PreflightStatus.BYTE_CAP_FAILURE, "maximum_bytes_billed_exceeded"),
    (RuntimeError("provider payload SECRET"),
     PreflightStatus.PROVIDER_QUERY_FAILURE, "bigquery_query_failed"),
])
def test_errors_are_classified_and_sanitized(failure, status, diagnostic):
    adapter = FakeAdapter("execution-project", failure=failure)
    result = GoogleTrendsRuntimePreflight(
        adapter_factory=factory_for(adapter), project_id="execution-project",
        refresh_date=date(2026, 9, 3),
    ).run()
    assert result.status == status
    assert result.diagnostic_code == diagnostic
    assert result.query_succeeded is False
    assert "SECRET" not in result.model_dump_json()
    assert len(adapter.calls) == 1


def test_client_construction_error_is_classified_and_sanitized():
    def failing_factory(_project_id):
        raise DefaultCredentialsError("private_key=SECRET token=SECRET")

    result = GoogleTrendsRuntimePreflight(
        adapter_factory=failing_factory, project_id="execution-project",
        refresh_date=date(2026, 9, 3),
    ).run()
    assert result.status == PreflightStatus.AUTHENTICATION_FAILURE
    assert result.diagnostic_code == "adc_authentication_failed"
    assert "SECRET" not in result.model_dump_json()


def test_runtime_does_not_persist_or_map_taxonomy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    adapter = FakeAdapter("execution-project", rows=[{"term": "unmapped provider term"}])
    before = list(tmp_path.rglob("*"))
    result = GoogleTrendsRuntimePreflight(
        adapter_factory=factory_for(adapter), project_id="execution-project",
        refresh_date=date(2026, 9, 3),
    ).run()
    assert result.evidence_available is True
    assert list(tmp_path.rglob("*")) == before
    assert not hasattr(result, "normalized_signals")


def test_existing_adapter_default_behavior_remains_compatible():
    class Row:
        def items(self):
            return {
                "refresh_date": date(2026, 9, 3), "week": date(2026, 8, 30),
                "dma_id": 1, "dma_name": "Test", "term": "term",
                "score": 1, "rank": 1, "percent_gain": 1,
            }.items()

    class Job:
        total_bytes_processed = 1
        total_bytes_billed = 1
        job_id = "job"
        def result(self): return [Row()]

    class Client:
        def query(self, query, *, job_config): return Job()

    adapter = GoogleTrendsBigQueryAdapter(
        "project", client=Client(), job_config_factory=lambda *args: args
    )
    assert len(adapter.retrieve(date(2026, 9, 3), row_limit=1).observations) == 1


def test_trend_signals_public_contract_remains_synthetic():
    body = TestClient(server.app).get("/trend-signals").json()
    assert body["data_source"] == "synthetic_demo"
    assert body["is_live_data"] is False
