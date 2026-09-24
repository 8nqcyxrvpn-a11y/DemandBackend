"""Versioned, exact-match production fashion taxonomy."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator

from app.brand_intelligence.models import DomainModel, _require_aware
from app.config import PROJECT_ROOT
from app.market_intelligence.models import MappingStatus
from app.market_intelligence.normalization import TaxonomyMappingRule

TAXONOMY_PATH = PROJECT_ROOT / "data/taxonomies/fashion/fashion_taxonomy_v1.json"


class FashionTaxonomyCategory(str, Enum):
    COLOR = "color"
    MATERIAL = "material"
    GARMENT = "garment"
    FOOTWEAR = "footwear"
    BAGS_ACCESSORIES = "bags_accessories"
    SILHOUETTE = "silhouette"
    PATTERN = "pattern"
    AESTHETIC_STYLE = "aesthetic_style"


def normalized_alias(value: str) -> str:
    return " ".join(value.casefold().split())


class FashionTaxonomyEntry(DomainModel):
    canonical_code: str = Field(pattern=r"^[a-z_]+:[a-z0-9_]+$")
    category: FashionTaxonomyCategory
    canonical_label: str = Field(min_length=1)
    aliases: list[str] = Field(min_length=1)
    approval_status: Literal["approved"] = "approved"

    @field_validator("aliases")
    @classmethod
    def aliases_are_unique_and_nonempty(cls, values: list[str]) -> list[str]:
        normalized = [normalized_alias(value) for value in values]
        if any(not value for value in normalized):
            raise ValueError("taxonomy aliases cannot be empty")
        if len(normalized) != len(set(normalized)):
            raise ValueError("taxonomy entry contains duplicate aliases")
        return values

    @model_validator(mode="after")
    def category_matches_code(self) -> "FashionTaxonomyEntry":
        if not self.canonical_code.startswith(f"{self.category.value}:"):
            raise ValueError("canonical code must use its taxonomy category prefix")
        return self


class ProductionFashionTaxonomy(DomainModel):
    artifact_kind: Literal["production_fashion_taxonomy"]
    taxonomy_version: Literal["fashion-taxonomy-1.0"]
    status: Literal["production_approved"]
    reviewed_at: datetime
    reviewed_by: str = Field(min_length=1)
    matching_method: Literal["casefolded_exact_alias"]
    entries_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    categories: list[FashionTaxonomyCategory] = Field(min_length=1)
    entries: list[FashionTaxonomyEntry] = Field(min_length=1)

    _reviewed_at_aware = field_validator("reviewed_at")(_require_aware)

    @model_validator(mode="after")
    def taxonomy_is_consistent(self) -> "ProductionFashionTaxonomy":
        if set(self.categories) != set(FashionTaxonomyCategory):
            raise ValueError("production taxonomy must declare every supported category")
        codes = [entry.canonical_code for entry in self.entries]
        if len(codes) != len(set(codes)):
            raise ValueError("production taxonomy contains duplicate canonical codes")
        aliases: dict[str, str] = {}
        for entry in self.entries:
            for alias in entry.aliases:
                key = normalized_alias(alias)
                if key in aliases:
                    raise ValueError("production taxonomy contains an ambiguous alias")
                aliases[key] = entry.canonical_code
        return self


@dataclass(frozen=True)
class FashionTaxonomyRegistry:
    taxonomy: ProductionFashionTaxonomy
    artifact_sha256: str
    rules: tuple[TaxonomyMappingRule, ...]
    entries_by_code: dict[str, FashionTaxonomyEntry]


def _entries_digest(entries: list[FashionTaxonomyEntry]) -> str:
    payload = [entry.model_dump(mode="json") for entry in entries]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@lru_cache(maxsize=1)
def load_production_fashion_taxonomy(
    path: Path = TAXONOMY_PATH,
) -> FashionTaxonomyRegistry:
    raw = path.read_bytes()
    taxonomy = ProductionFashionTaxonomy.model_validate_json(raw, strict=True)
    if _entries_digest(taxonomy.entries) != taxonomy.entries_sha256:
        raise ValueError("fashion taxonomy entries hash mismatch")
    rules = tuple(
        TaxonomyMappingRule(
            rule_id=f"{taxonomy.taxonomy_version}:{entry.canonical_code}:alias-{index}",
            signal_type="search_interest",
            source_term=alias,
            canonical_code=entry.canonical_code,
            taxonomy_version=taxonomy.taxonomy_version,
            review_status=MappingStatus.REVIEWED,
            reviewed_by=taxonomy.reviewed_by,
        )
        for entry in taxonomy.entries
        for index, alias in enumerate(entry.aliases, start=1)
    )
    return FashionTaxonomyRegistry(
        taxonomy=taxonomy,
        artifact_sha256=hashlib.sha256(raw).hexdigest(),
        rules=rules,
        entries_by_code={entry.canonical_code: entry for entry in taxonomy.entries},
    )
