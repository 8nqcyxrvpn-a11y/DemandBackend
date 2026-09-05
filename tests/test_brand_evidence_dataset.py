import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.brand_intelligence.datasets import load_evidence_dataset
from app.brand_intelligence.models import BrandEvidenceDataset


DATASET = Path(__file__).parents[1] / "data/brand_evidence/hermes/validation_v1.json"


def test_real_validation_sample_is_provenance_complete():
    dataset = load_evidence_dataset(DATASET)

    assert dataset.brand.validation_case is True
    assert len(dataset.assortment) == 12
    assert len(dataset.prices) == 12
    assert all(source.is_official for source in dataset.sources)
    assert all(source.capture_method.value == "manual" for source in dataset.sources)
    assert all(source.source_url.host == "www.hermes.com" for source in dataset.sources)
    assert all(item.global_availability == "unknown" for item in dataset.assortment)
    assert all(price.market_region == "US" and price.currency == "USD" for price in dataset.prices)
    assert all(trait.status.value == "candidate" for trait in dataset.dna_traits)


def test_dataset_rejects_broken_evidence_reference():
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    payload["assortment"][0]["attributes"][0]["supporting_evidence_ids"] = ["missing"]

    with pytest.raises(ValidationError, match="unknown evidence ID"):
        BrandEvidenceDataset.model_validate(payload)


def test_dataset_rejects_evidence_source_url_mismatch():
    payload = json.loads(DATASET.read_text(encoding="utf-8"))
    payload["evidence"][0]["source_url"] = "https://www.hermes.com/us/en/"

    with pytest.raises(ValidationError, match="source URL mismatch"):
        BrandEvidenceDataset.model_validate(payload)
