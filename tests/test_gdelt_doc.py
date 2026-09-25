import hashlib
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app.market_intelligence.aggregation import derive_temporal_metrics
from app.market_intelligence.fashion_taxonomy import load_production_fashion_taxonomy
from app.market_intelligence.gdelt_doc import (
    ENDPOINT, GdeltDocAdapter, GdeltProviderError, gdelt_taxonomy_rules,
)
from app.market_intelligence.models import MappingStatus, MarketSignalType, TrendMetricStatus
from app.market_intelligence.normalization import normalize_observation

NOW = datetime(2026, 9, 25, 12, tzinfo=timezone.utc)
START = NOW - timedelta(days=30)


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self.content = json.dumps(payload, sort_keys=True).encode()
        self.status_code = status_code
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "secret provider body", request=httpx.Request("GET", ENDPOINT),
                response=httpx.Response(self.status_code),
            )

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, payload, status_code=200):
        self.response = FakeResponse(payload, status_code)
        self.calls = []

    def get(self, url, *, params):
        self.calls.append((url, params))
        return self.response


class FailingClient:
    def __init__(self, error):
        self.error = error
        self.calls = []

    def get(self, url, *, params):
        self.calls.append((url, params))
        raise self.error


def payload(*values):
    return {"timeline": [{"series": "Volume Intensity", "data": [
        {"date": f"2026092{index}T000000Z", "value": value, "norm": 1000}
        for index, value in enumerate(values, start=1)
    ]}]}


def test_exact_phrase_request_and_raw_provenance_are_preserved():
    client = FakeClient(payload(3, 5, 9))
    result = GdeltDocAdapter(client=client).retrieve(
        " suede   jacket ", start=START, end=NOW, retrieved_at=NOW
    )
    assert len(client.calls) == 1
    url, params = client.calls[0]
    assert url == ENDPOINT
    assert params == {
        "query": '"suede jacket"', "mode": "timelinevolraw", "format": "json",
        "startdatetime": "20260826120000", "enddatetime": "20260925120000",
        "timelinesmooth": "0",
    }
    assert result.raw_response_sha256 == hashlib.sha256(client.response.content).hexdigest()
    assert result.source.source_id == "gdelt-doc-2-timelinevolraw"
    assert result.source.provider == "GDELT Project"
    observation = result.observations[0]
    assert observation.raw_signal == "suede jacket"
    assert observation.signal_type.value == "editorial_media_attention"
    assert observation.raw_observed_value["article_count"] == 3
    assert observation.raw_observed_value["monitored_article_count"] == 1000
    assert observation.raw_observed_value["raw_response_sha256"] == result.raw_response_sha256
    assert observation.normalized_value == pytest.approx(0.3)
    assert "not consumer demand or sales" in observation.unit_definition
    assert not observation.is_fixture and not observation.is_synthetic


def test_only_explicit_taxonomy_alias_resolves_and_no_fuzzy_matching_occurs():
    registry = load_production_fashion_taxonomy()
    rules = gdelt_taxonomy_rules(registry.rules)
    exact = GdeltDocAdapter(client=FakeClient(payload(2))).retrieve(
        "SUEDE JACKET", start=START, end=NOW, retrieved_at=NOW
    ).observations[0]
    unrelated = exact.model_copy(update={"observation_id": "other", "raw_signal": "celebrity suede look"})
    mapped = normalize_observation(exact, rules, taxonomy_version=registry.taxonomy.taxonomy_version)
    unresolved = normalize_observation(
        unrelated, rules, taxonomy_version=registry.taxonomy.taxonomy_version
    )
    assert mapped.mapping_status == MappingStatus.REVIEWED
    assert mapped.canonical_code == "garment:suede_jacket"
    assert unresolved.mapping_status == MappingStatus.UNRESOLVED
    assert unresolved.canonical_code is None


def test_ambiguous_rules_remain_ambiguous():
    registry = load_production_fashion_taxonomy()
    rules = gdelt_taxonomy_rules(registry.rules)
    base = next(rule for rule in rules if rule.source_term == "suede jacket")
    rules.append(base.model_copy(update={"rule_id": "conflict", "canonical_code": "material:suede"}))
    observation = GdeltDocAdapter(client=FakeClient(payload(2))).retrieve(
        "suede jacket", start=START, end=NOW, retrieved_at=NOW
    ).observations[0]
    mapped = normalize_observation(observation, rules, taxonomy_version="fashion-taxonomy-1.0")
    assert mapped.mapping_status == MappingStatus.AMBIGUOUS
    assert mapped.canonical_code is None


def test_gdelt_alone_remains_insufficient_and_google_can_only_add_real_breadth():
    registry = load_production_fashion_taxonomy()
    rules = gdelt_taxonomy_rules(registry.rules)
    observations = GdeltDocAdapter(client=FakeClient(payload(2, 3, 4))).retrieve(
        "suede jacket", start=START, end=NOW, retrieved_at=NOW
    ).observations
    mapped = [normalize_observation(item, rules, taxonomy_version="fashion-taxonomy-1.0")
              for item in observations]
    metrics = derive_temporal_metrics("garment:suede_jacket", mapped, observations, calculated_at=NOW)
    assert metrics.source_breadth == 1
    assert metrics.status == TrendMetricStatus.INSUFFICIENT_EVIDENCE
    assert metrics.is_live_data is False

    google = observations[-1].model_copy(update={
        "observation_id": "google-independent-observation",
        "source_id": "google-trends-bigquery-top-rising",
        "signal_type": MarketSignalType.SEARCH_INTEREST,
        "period_start": observations[-1].period_start + timedelta(days=1),
        "period_end": observations[-1].period_end + timedelta(days=1),
        "methodology_version": "google-trends-bigquery-taxonomy-priority-v1",
        "raw_observed_value": {"score": 40},
        "normalized_value": 40,
    })
    google_rule = next(
        rule for rule in registry.rules if rule.source_term == "suede jacket"
    )
    combined_observations = observations + [google]
    combined_mapped = mapped + [normalize_observation(
        google, [google_rule], taxonomy_version="fashion-taxonomy-1.0"
    )]
    corroborated = derive_temporal_metrics(
        "garment:suede_jacket", combined_mapped, combined_observations, calculated_at=NOW
    )
    assert corroborated.source_breadth == 2
    assert corroborated.status == TrendMetricStatus.SUFFICIENT
    assert corroborated.signal_type.value == "market_attention"
    assert any("provider-specific scales" in item for item in corroborated.limitations)


def test_empty_timeline_is_valid_no_observations_and_malformed_data_fails_closed():
    empty = GdeltDocAdapter(client=FakeClient({"timeline": []})).retrieve(
        "loafers", start=START, end=NOW, retrieved_at=NOW
    )
    assert empty.observations == []
    with pytest.raises(GdeltProviderError, match="failure=missing_timeline"):
        GdeltDocAdapter(client=FakeClient({})).retrieve(
            "loafers", start=START, end=NOW, retrieved_at=NOW
        )


def test_provider_errors_are_sanitized_and_no_retry_occurs():
    client = FakeClient({"secret": "must-not-leak"}, status_code=503)
    with pytest.raises(GdeltProviderError) as caught:
        GdeltDocAdapter(client=client).retrieve(
            "loafers", start=START, end=NOW, retrieved_at=NOW
        )
    assert len(client.calls) == 1
    assert "secret" not in str(caught.value)
    assert "failure=http_status" in str(caught.value)
    assert "http_status=503" in str(caught.value)


@pytest.mark.parametrize(
    ("error", "failure", "exception_type"),
    [
        (httpx.ConnectTimeout("secret URL"), "connect_timeout", "ConnectTimeout"),
        (httpx.ReadTimeout("secret response"), "read_timeout", "ReadTimeout"),
        (httpx.ConnectError("secret TLS detail"), "connect_error", "ConnectError"),
    ],
)
def test_transport_diagnostics_preserve_safe_type_without_leaking_details(
    error, failure, exception_type
):
    client = FailingClient(error)
    with pytest.raises(GdeltProviderError) as caught:
        GdeltDocAdapter(client=client).retrieve(
            "suede jacket", start=START, end=NOW, retrieved_at=NOW
        )
    diagnostic = str(caught.value)
    assert f"failure={failure}" in diagnostic
    assert f"exception_type={exception_type}" in diagnostic
    assert "secret" not in diagnostic
    assert len(client.calls) == 1


@pytest.mark.parametrize("phrase", ["", "   ", 'bad " phrase'])
def test_invalid_phrases_fail_before_transport(phrase):
    client = FakeClient(payload(1))
    with pytest.raises(ValueError):
        GdeltDocAdapter(client=client).retrieve(phrase, start=START, end=NOW)
    assert client.calls == []
