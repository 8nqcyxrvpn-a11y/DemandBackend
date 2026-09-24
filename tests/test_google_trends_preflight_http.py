from __future__ import annotations

from datetime import date

from fastapi import FastAPI
from fastapi.testclient import TestClient

import server
from app.market_intelligence.google_trends_preflight_http import (
    ENABLE_ENV,
    ROUTE,
    SECRET_ENV,
    SECRET_HEADER,
    register_google_trends_preflight_route,
)
from app.market_intelligence.google_trends_runtime import (
    GoogleTrendsPreflightResult,
    PreflightStatus,
)

TEST_SECRET = "test-only-high-entropy-secret-value-1234567890"


class FakeRuntime:
    def __init__(self, calls: list[str]) -> None:
        self._calls = calls

    def run(self) -> GoogleTrendsPreflightResult:
        self._calls.append("run")
        return GoogleTrendsPreflightResult(
            status=PreflightStatus.SUCCESS_ROWS,
            query_succeeded=True,
            evidence_available=True,
            row_count=1,
            source_id="google-trends-bigquery-top-rising",
            dataset_identifier="bigquery-public-data.google_trends.top_rising_terms",
            methodology_version="google-trends-bigquery-top-rising-v1",
            refresh_date=date(2026, 9, 3).isoformat(),
            row_limit=1,
            total_bytes_processed=100,
            total_bytes_billed=100,
            job_id_present=True,
            diagnostic_code="query_completed_with_rows",
        )


def build_app(monkeypatch, *, enabled: bool, calls: list[str]) -> FastAPI:
    if enabled:
        monkeypatch.setenv(ENABLE_ENV, "true")
    else:
        monkeypatch.delenv(ENABLE_ENV, raising=False)
    app = FastAPI()
    register_google_trends_preflight_route(
        app, runtime_factory=lambda: FakeRuntime(calls),
    )
    return app


def test_endpoint_absent_when_disabled(monkeypatch):
    calls: list[str] = []
    app = build_app(monkeypatch, enabled=False, calls=calls)
    response = TestClient(app).post(ROUTE)
    assert response.status_code == 404
    assert ROUTE not in TestClient(app).get("/openapi.json").json()["paths"]
    assert calls == []


def test_enabled_endpoint_is_absent_from_openapi(monkeypatch):
    app = build_app(monkeypatch, enabled=True, calls=[])
    assert ROUTE not in TestClient(app).get("/openapi.json").json()["paths"]


def test_missing_or_wrong_secret_never_runs_preflight(monkeypatch):
    calls: list[str] = []
    app = build_app(monkeypatch, enabled=True, calls=calls)
    monkeypatch.setenv(SECRET_ENV, TEST_SECRET)
    client = TestClient(app)
    assert client.post(ROUTE).status_code == 404
    assert client.post(ROUTE, headers={SECRET_HEADER: "wrong-secret"}).status_code == 404
    assert calls == []


def test_short_server_secret_fails_closed_without_running_preflight(monkeypatch):
    calls: list[str] = []
    app = build_app(monkeypatch, enabled=True, calls=calls)
    monkeypatch.setenv(SECRET_ENV, "too-short")
    response = TestClient(app).post(ROUTE, headers={SECRET_HEADER: "too-short"})
    assert response.status_code == 503
    assert calls == []


def test_correct_secret_invokes_once_and_returns_only_sanitized_result(monkeypatch):
    calls: list[str] = []
    app = build_app(monkeypatch, enabled=True, calls=calls)
    monkeypatch.setenv(SECRET_ENV, TEST_SECRET)
    response = TestClient(app).post(ROUTE, headers={SECRET_HEADER: TEST_SECRET})
    assert response.status_code == 200
    assert calls == ["run"]
    assert response.json() == {
        "status": "success_rows",
        "query_succeeded": True,
        "evidence_available": True,
        "row_count": 1,
        "source_id": "google-trends-bigquery-top-rising",
        "dataset_identifier": "bigquery-public-data.google_trends.top_rising_terms",
        "methodology_version": "google-trends-bigquery-top-rising-v1",
        "refresh_date": "2026-09-03",
        "row_limit": 1,
        "total_bytes_processed": 100,
        "total_bytes_billed": 100,
        "job_id_present": True,
        "diagnostic_code": "query_completed_with_rows",
    }
    serialized = response.text
    assert TEST_SECRET not in serialized
    assert "credentials" not in serialized
    assert "observations" not in serialized
    assert "raw_rows" not in serialized


def test_production_app_trend_signals_remains_synthetic_and_route_is_disabled():
    client = TestClient(server.app)
    body = client.get("/trend-signals").json()
    assert body["data_source"] == "synthetic_demo"
    assert body["is_live_data"] is False
    assert client.post(ROUTE).status_code == 404
    assert ROUTE not in client.get("/openapi.json").json()["paths"]
