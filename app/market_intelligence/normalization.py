"""Deterministic, reviewable taxonomy normalization without fuzzy inference."""

from __future__ import annotations

from typing import Optional

from pydantic import Field, model_validator

from app.brand_intelligence.models import DomainModel
from app.market_intelligence.models import MappingStatus, MarketObservation, NormalizedMarketSignal


class TaxonomyMappingRule(DomainModel):
    rule_id: str = Field(min_length=1)
    signal_type: str = Field(min_length=1)
    source_term: str = Field(min_length=1)
    canonical_code: str = Field(min_length=1)
    taxonomy_version: str = Field(min_length=1)
    review_status: MappingStatus = MappingStatus.EXACT
    reviewed_by: Optional[str] = None

    @model_validator(mode="after")
    def rule_must_be_resolved(self) -> "TaxonomyMappingRule":
        if self.review_status not in {MappingStatus.EXACT, MappingStatus.REVIEWED}:
            raise ValueError("mapping rules must be exact or human-reviewed")
        if self.review_status == MappingStatus.REVIEWED and not self.reviewed_by:
            raise ValueError("reviewed mapping rules require reviewer identity")
        return self


def _key(value: str) -> str:
    return " ".join(value.casefold().split())


def normalize_observation(
    observation: MarketObservation,
    rules: list[TaxonomyMappingRule],
    *,
    taxonomy_version: str,
) -> NormalizedMarketSignal:
    matches = [
        rule for rule in rules
        if rule.signal_type == observation.signal_type.value
        and _key(rule.source_term) == _key(observation.raw_signal)
        and rule.taxonomy_version == taxonomy_version
    ]
    codes = {rule.canonical_code for rule in matches}
    if not matches:
        status, code, rule_id, reviewer = MappingStatus.UNRESOLVED, None, None, None
    elif len(codes) > 1:
        status, code, rule_id, reviewer = MappingStatus.AMBIGUOUS, None, None, None
    else:
        rule = sorted(matches, key=lambda item: item.rule_id)[0]
        status, code, rule_id, reviewer = (
            rule.review_status, rule.canonical_code, rule.rule_id, rule.reviewed_by
        )
    return NormalizedMarketSignal(
        normalized_signal_id=f"normalized:{observation.observation_id}:{taxonomy_version}",
        observation_id=observation.observation_id,
        signal_type=observation.signal_type,
        raw_signal=observation.raw_signal,
        canonical_code=code,
        taxonomy_version=taxonomy_version,
        mapping_status=status,
        mapping_rule_id=rule_id,
        reviewed_by=reviewer,
    )
