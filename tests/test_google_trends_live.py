from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

import server
from app.brand_intelligence.enums import EvidenceStatus
from app.market_intelligence.google_trends_bigquery import GoogleTrendsBigQueryAdapter
from app.market_intelligence.google_trends_live import (
    LIVE_DMA_SAMPLE_LIMIT,
    LIVE_ROW_LIMIT,
    GoogleTrendsLiveService,
    GoogleTrendsLiveServiceError,
    select_start_date,
)
from app.market_intelligence.models import MappingStatus, TrendMetricStatus
from app.market_intelligence.normalization import TaxonomyMappingRule

NOW = datetime(2026, 9, 25, 12, tzinfo=timezone.utc)


class FakeRow:
    def __init__(self, term: str, *, week: date = date(2026, 9, 20)) -> None:
        self.values = {
            "refresh_date": date(2026, 9, 22),
            "week": week,
            "dma_id": 501,
            "dma_name": "New York NY",
            "term": term,
            "score": 80,
            "rank": 1,
            "percent_gain": 120,
        }

    def items(self):
        return self.values.items()


class FakeJob:
    total_bytes_processed = 100
    total_bytes_billed = 100
    job_id = "fake-job"

    def __init__(self, rows):
        self._rows = rows

    def result(self):
        return self._rows


class FakeClient:
    def __init__(self, rows_by_date=None, failure=None):
        self.rows_by_date = rows_by_date or {}
        self.failure = failure
        self.calls = []

    def query(self, query, *, job_config):
        self.calls.append((query, job_config))
        if self.failure:
            raise self.failure
        refresh_date = job_config[0]
        return FakeJob(self.rows_by_date.get(refresh_date, []))


def adapter_factory(client):
    def factory(project_id):
        assert project_id == "test-project"
        return GoogleTrendsBigQueryAdapter(
            project_id, client=client, job_config_factory=lambda refresh, limit, cap: (
                refresh, limit, cap
            ),
            priority_job_config_factory=lambda refresh, limit, cap, terms, dma_limit: (
                refresh, limit, cap, terms, dma_limit
            ),
        )
    return factory


def build_service(monkeypatch, client, *, rules=None):
    monkeypatch.setenv("GOOGLE_TRENDS_BIGQUERY_PROJECT_ID", "test-project")
    monkeypatch.setenv("GOOGLE_TRENDS_REFRESH_DATE", "2026-09-24")
    return GoogleTrendsLiveService(
        adapter_factory=adapter_factory(client), taxonomy_rules=rules,
        clock=lambda: NOW,
    )


def test_successful_live_retrieval_preserves_provenance_and_reality(monkeypatch):
    client = FakeClient({date(2026, 9, 24): [FakeRow("arbitrary news topic")]})
    response = build_service(monkeypatch, client).load()
    observation = response.observations[0]
    assert response.is_live_data is True
    assert response.batch_version == "google-trends-live-v1"
    assert response.refresh_date_used == date(2026, 9, 24)
    assert observation.source_id == response.source.source_id
    assert observation.dataset_identifier == response.source.dataset_identifier
    assert observation.retrieved_at == NOW
    assert observation.period_start.isoformat().startswith("2026-09-20")
    assert observation.geography == "US DMA 501: New York NY"
    assert observation.raw_signal == "arbitrary news topic"
    assert observation.raw_observed_value["percent_gain"] == 120
    assert observation.methodology_version == response.source.methodology_version
    assert observation.verification_status == EvidenceStatus.VERIFIED
    assert observation.is_fixture is False and observation.is_synthetic is False
    assert response.normalized_signals[0].mapping_status == MappingStatus.UNRESOLVED
    assert response.raw_observation_count == 1
    assert response.resolved_fashion_signal_count == 0
    assert response.unresolved_count == 1
    assert response.ambiguous_count == 0
    assert response.unresolved_observations == response.observations
    assert response.derived_metrics == []
    assert response.evidence_sufficient_for_derived_metrics is False
    assert client.calls[0][1][1:3] == (LIVE_ROW_LIMIT, 109_051_904)
    assert "silk" in client.calls[0][1][3]
    assert client.calls[0][1][4] == LIVE_DMA_SAMPLE_LIMIT


def test_recent_date_fallback_is_bounded_and_explicit(monkeypatch):
    client = FakeClient({date(2026, 9, 22): [FakeRow("unmapped")]})
    response = build_service(monkeypatch, client).load()
    assert response.refresh_date_requested == date(2026, 9, 24)
    assert response.refresh_date_used == date(2026, 9, 22)
    assert response.attempted_refresh_dates == [
        date(2026, 9, 24), date(2026, 9, 23), date(2026, 9, 22)
    ]
    assert len(client.calls) == 3


def test_stale_configuration_uses_current_date_and_invalid_fails(monkeypatch):
    monkeypatch.setenv("GOOGLE_TRENDS_REFRESH_DATE", "2020-01-01")
    assert select_start_date(today=NOW.date()) == NOW.date()
    monkeypatch.setenv("GOOGLE_TRENDS_REFRESH_DATE", "not-a-date")
    with pytest.raises(GoogleTrendsLiveServiceError) as error:
        select_start_date(today=NOW.date())
    assert error.value.diagnostic_code == "invalid_refresh_date_configuration"


def test_production_rule_is_case_insensitive_but_exact_and_stays_insufficient(monkeypatch):
    client = FakeClient({date(2026, 9, 24): [FakeRow("SILK")]})
    response = build_service(monkeypatch, client).load()
    normalized = response.normalized_signals[0]
    assert normalized.mapping_status == MappingStatus.REVIEWED
    assert normalized.canonical_code == "material:silk"
    assert response.resolved_fashion_signal_count == 1
    assert response.unresolved_count == 0
    assert response.resolved_fashion_signals[0].taxonomy_category == "material"
    assert response.resolved_fashion_signals[0].observation_id == normalized.observation_id
    assert response.resolved_fashion_signals[0].source_id == response.source.source_id
    assert response.taxonomy_artifact_sha256 == (
        response.resolved_fashion_signals[0].taxonomy_artifact_sha256
    )
    assert response.derived_metrics[0].status == TrendMetricStatus.INSUFFICIENT_EVIDENCE
    assert response.derived_metrics[0].source_breadth == 1
    assert response.derived_metrics[0].is_live_data is False
    assert response.evidence_sufficient_for_derived_metrics is False


def test_no_fuzzy_inference_and_nonfashion_terms_remain_unresolved(monkeypatch):
    rows = [
        FakeRow("best silk dresses 2026"),
        FakeRow("Taylor Swift"),
        FakeRow("weather tomorrow"),
    ]
    client = FakeClient({date(2026, 9, 24): rows})
    response = build_service(monkeypatch, client).load()
    assert response.raw_observation_count == 3
    assert response.resolved_fashion_signal_count == 0
    assert response.unresolved_count == 3
    assert {item.raw_signal for item in response.unresolved_observations} == {
        "best silk dresses 2026", "Taylor Swift", "weather tomorrow"
    }


def test_prioritized_retrieval_maps_exact_fashion_and_keeps_general_unresolved(monkeypatch):
    rows = [FakeRow("suede jacket"), FakeRow("general election results")]
    client = FakeClient({date(2026, 9, 24): rows})
    response = build_service(monkeypatch, client).load()
    assert response.raw_observation_count == 2
    assert response.resolved_fashion_signal_count == 1
    assert response.unresolved_count == 1
    assert response.resolved_fashion_signals[0].canonical_code == "garment:suede_jacket"
    assert response.unresolved_observations[0].raw_signal == "general election results"
    assert response.evidence_sufficient_for_derived_metrics is False


def test_conflicting_explicit_rules_remain_ambiguous(monkeypatch):
    rules = [
        TaxonomyMappingRule(
            rule_id="silk-material", signal_type="search_interest",
            source_term="silk", canonical_code="material:silk",
            taxonomy_version="fashion-taxonomy-1.0",
        ),
        TaxonomyMappingRule(
            rule_id="silk-aesthetic", signal_type="search_interest",
            source_term="silk", canonical_code="aesthetic:silk",
            taxonomy_version="fashion-taxonomy-1.0",
        ),
    ]
    client = FakeClient({date(2026, 9, 24): [FakeRow("silk")]})
    response = build_service(monkeypatch, client, rules=rules).load()
    assert response.normalized_signals[0].mapping_status == MappingStatus.AMBIGUOUS
    assert response.normalized_signals[0].canonical_code is None
    assert response.derived_metrics == []
    assert response.ambiguous_count == 1
    assert response.unresolved_count == 0


class PermissionDenied(Exception):
    pass


class DefaultCredentialsError(Exception):
    pass


@pytest.mark.parametrize(("failure", "diagnostic"), [
    (PermissionDenied("secret provider details"), "bigquery_permission_denied"),
    (DefaultCredentialsError("private key material"), "adc_authentication_failed"),
])
def test_provider_failures_are_sanitized_and_not_retried(monkeypatch, failure, diagnostic):
    client = FakeClient(failure=failure)
    service = build_service(monkeypatch, client)
    with pytest.raises(GoogleTrendsLiveServiceError) as error:
        service.load()
    assert error.value.diagnostic_code == diagnostic
    assert str(failure) not in str(error.value)
    assert len(client.calls) == 1


def test_api_response_and_failures_do_not_leak_secrets(monkeypatch):
    response = build_service(
        monkeypatch,
        FakeClient({date(2026, 9, 24): [FakeRow("unmapped")]}),
    ).load()
    monkeypatch.setattr(server, "load_google_trends_market_evidence", lambda: response)
    client = TestClient(server.app)
    result = client.get("/market-intelligence/google-trends")
    assert result.status_code == 200
    assert "secret" not in result.text.casefold()
    assert "credential" not in result.text.casefold()
    assert result.json()["normalized_signals"][0]["mapping_status"] == "unresolved"
    assert result.json()["raw_observation_count"] == 1
    assert result.json()["resolved_fashion_signal_count"] == 0
    assert result.json()["unresolved_count"] == 1

    def fail():
        raise GoogleTrendsLiveServiceError("bigquery_permission_denied")

    monkeypatch.setattr(server, "load_google_trends_market_evidence", fail)
    failed = client.get("/market-intelligence/google-trends")
    assert failed.status_code == 503
    assert failed.json() == {"detail": {
        "message": "Google Trends market evidence is unavailable.",
        "diagnostic_code": "bigquery_permission_denied",
    }}


def test_existing_trend_signals_stays_explicitly_synthetic():
    body = TestClient(server.app).get("/trend-signals").json()
    assert body["data_source"] == "synthetic_demo"
    assert body["is_live_data"] is False
