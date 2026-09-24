from __future__ import annotations

import json

import pytest

from app.market_intelligence.fashion_taxonomy import (
    FashionTaxonomyCategory,
    TAXONOMY_PATH,
    load_production_fashion_taxonomy,
)


def test_production_taxonomy_is_versioned_complete_and_hash_validated():
    registry = load_production_fashion_taxonomy()
    taxonomy = registry.taxonomy
    assert taxonomy.taxonomy_version == "fashion-taxonomy-1.0"
    assert taxonomy.status == "production_approved"
    assert taxonomy.matching_method == "casefolded_exact_alias"
    assert set(taxonomy.categories) == set(FashionTaxonomyCategory)
    assert len(taxonomy.entries) == 29
    assert len(registry.artifact_sha256) == 64
    assert all(rule.review_status.value == "reviewed" for rule in registry.rules)


def test_expected_explicit_aliases_are_present_without_person_names():
    registry = load_production_fashion_taxonomy()
    aliases = {rule.source_term.casefold(): rule.canonical_code for rule in registry.rules}
    assert aliases["butter yellow"] == "color:butter_yellow"
    assert aliases["suede jacket"] == "garment:suede_jacket"
    assert aliases["wide-leg trousers"] == "garment:wide_leg_trousers"
    assert aliases["ballet flats"] == "footwear:ballet_flats"
    assert aliases["shoulder bag"] == "bags_accessories:shoulder_bag"
    assert aliases["narrow silhouette"] == "silhouette:slim_narrow"
    assert aliases["quiet luxury"] == "aesthetic_style:quiet_luxury"
    assert "taylor swift" not in aliases


def test_tampered_taxonomy_hash_fails_closed(tmp_path):
    payload = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    payload["entries"][0]["aliases"].append("tampered alias")
    path = tmp_path / "taxonomy.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        load_production_fashion_taxonomy(path)
