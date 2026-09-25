import json
from datetime import date, datetime, timezone
from pathlib import Path

from app.market_intelligence.google_trends_bigquery import (
    DATASET_IDENTIFIER,
    GoogleTrendsBigQueryAdapter,
    PRIORITIZED_METHODOLOGY_VERSION,
    PRIORITIZED_QUERY,
    QUERY,
)
from app.market_intelligence.models import MappingStatus, MarketEvidenceBatch
from app.market_intelligence.normalization import normalize_observation


NOW = datetime(2026, 9, 5, 22, 38, 21, tzinfo=timezone.utc)
RAW_PATH = Path(__file__).parents[1] / (
    "data/market_evidence/google_trends/validation_2026-09-06/raw_response.json"
)


class FakeRow:
    def __init__(self, values):
        self.values = values

    def items(self):
        return self.values.items()


class FakeJob:
    job_id = "test-job"
    total_bytes_processed = 108_329_774
    total_bytes_billed = 109_051_904

    def __init__(self, rows):
        self.rows = rows

    def result(self):
        return [FakeRow(row) for row in self.rows]


class FakeClient:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def query(self, query, *, job_config):
        self.calls.append((query, job_config))
        return FakeJob(self.rows)


def test_adapter_preserves_real_raw_provenance_and_leaves_mapping_unresolved():
    payload = json.loads(RAW_PATH.read_text(encoding="utf-8"))
    client = FakeClient(payload["rows"])
    adapter = GoogleTrendsBigQueryAdapter(
        "generic-project",
        client=client,
        job_config_factory=lambda refresh, limit, cap: {
            "refresh_date": refresh, "limit": limit, "maximum_bytes_billed": cap
        },
    )

    result = adapter.retrieve(date(2026, 9, 3), row_limit=5, retrieved_at=NOW)

    assert client.calls[0][0] == QUERY
    assert len(result.raw_rows) == len(result.observations) == 5
    assert result.total_bytes_processed == payload["total_bytes_processed"]
    assert result.source.dataset_identifier == DATASET_IDENTIFIER
    assert all(not item.is_fixture and not item.is_synthetic for item in result.observations)
    assert all(item.geography.startswith("US DMA") for item in result.observations)
    assert all(item.source_quality is None for item in result.observations)

    mapped = normalize_observation(
        result.observations[0], [], taxonomy_version="fashion-taxonomy-1.0"
    )
    assert mapped.mapping_status == MappingStatus.UNRESOLVED
    assert mapped.canonical_code is None

    batch = MarketEvidenceBatch(
        batch_id="google-trends-validation",
        batch_version="1",
        created_at=NOW,
        sources=[result.source],
        observations=result.observations,
        normalized_signals=[mapped],
    )
    assert batch.observations[0].raw_signal == "spaghetto"


def test_adapter_observation_ids_are_reproducible():
    rows = json.loads(RAW_PATH.read_text(encoding="utf-8"))["rows"]
    first = GoogleTrendsBigQueryAdapter(
        "project-a", client=FakeClient(rows), job_config_factory=lambda *args: args
    ).retrieve(date(2026, 9, 3), row_limit=5, retrieved_at=NOW)
    second = GoogleTrendsBigQueryAdapter(
        "project-b", client=FakeClient(rows), job_config_factory=lambda *args: args
    ).retrieve(date(2026, 9, 3), row_limit=5, retrieved_at=NOW)

    assert [item.observation_id for item in first.observations] == [
        item.observation_id for item in second.observations
    ]


def test_saved_query_and_raw_sample_match_execution_scope():
    query_path = RAW_PATH.with_name("query.sql")
    query = query_path.read_text(encoding="utf-8")
    payload = json.loads(RAW_PATH.read_text(encoding="utf-8"))

    assert "top_rising_terms" in query
    assert 'DATE "2026-09-03"' in query
    assert "LIMIT 5" in query
    assert payload["total_bytes_processed"] == 108_329_774
    assert len(payload["rows"]) == 5


def test_prioritized_retrieval_uses_exact_terms_and_bounded_dma_sampling():
    rows = [{
        "refresh_date": date(2026, 9, 22), "week": date(2026, 9, 20),
        "dma_id": 501, "dma_name": "New York NY", "term": "Suede Jacket",
        "score": 75, "rank": 4, "percent_gain": 160,
        "taxonomy_alias_match": True,
    }]
    client = FakeClient(rows)
    configs = []
    adapter = GoogleTrendsBigQueryAdapter(
        "project", client=client, job_config_factory=lambda *args: args,
        priority_job_config_factory=lambda *args: configs.append(args) or args,
    )
    result = adapter.retrieve_prioritizing_terms(
        date(2026, 9, 22),
        exact_terms=[" suede   jacket ", "SUEDE JACKET", "loafers"],
        row_limit=25,
        dma_sample_limit=3,
        retrieved_at=NOW,
    )
    assert client.calls[0][0] == PRIORITIZED_QUERY
    assert configs == [(date(2026, 9, 22), 25, 109_051_904,
                        ["loafers", "suede jacket"], 3)]
    assert result.source.methodology_version == PRIORITIZED_METHODOLOGY_VERSION
    assert result.observations[0].methodology_version == PRIORITIZED_METHODOLOGY_VERSION
    assert result.observations[0].raw_observed_value["taxonomy_alias_match"] is True
    assert "IN UNNEST(@exact_terms)" in result.query
    assert "term_week_dma_row <= @dma_sample_limit" in result.query


def test_null_score_is_preserved_as_missing_not_zero():
    row = {
        "refresh_date": date(2026, 9, 22), "week": date(2026, 9, 20),
        "dma_id": 501, "dma_name": "New York NY", "term": "loafers",
        "score": None, "rank": 4, "percent_gain": 160,
    }
    adapter = GoogleTrendsBigQueryAdapter(
        "project", client=FakeClient([row]), job_config_factory=lambda *args: args
    )
    observation = adapter.retrieve(date(2026, 9, 22), retrieved_at=NOW).observations[0]
    assert observation.raw_observed_value["score"] is None
    assert observation.normalized_value is None
