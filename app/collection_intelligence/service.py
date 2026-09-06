"""Deterministic ranking, duplicate rejection, quotas, and portfolio diversity."""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone

from app.collection_intelligence.models import (
    CollectionBrief,
    GeneratedCollection,
    ProductConcept,
    SyntheticTrendSignal,
)

METHODOLOGY_VERSION = "synthetic-creative-collection-selection-2.0"
_WORDS = re.compile(r"[a-z0-9]+")


class CollectionGenerationError(ValueError):
    """Raised when the requested portfolio cannot satisfy its guardrails."""


def _tokens(concept: ProductConcept) -> set[str]:
    return set(_WORDS.findall(f"{concept.core_idea} {concept.innovation}".casefold()))


def _similarity(left: ProductConcept, right: ProductConcept) -> float:
    a, b = _tokens(left), _tokens(right)
    return len(a & b) / len(a | b) if a or b else 1.0


def _rank(concept: ProductConcept, brief: CollectionBrief) -> ProductConcept:
    weights = brief.score_weights
    base = (
        concept.commercial_potential_score * weights["commercial_potential"]
        + concept.originality_score * weights["originality"]
        + concept.brand_coherence_score * weights["brand_coherence"]
        + concept.trend_score * weights["trend_alignment"]
        + concept.silhouette_distinctiveness_score * weights["silhouette_distinctiveness"]
        + concept.construction_novelty_score * weights["construction_novelty"]
        + concept.shape_recognizability_score * weights["shape_recognizability"]
        + concept.manufacturability_score * weights["manufacturability"]
    )
    penalty = (
        concept.generic_mass_market_risk * 0.15
        + concept.iconic_product_resemblance_risk * 0.20
        + concept.gimmick_weak_use_case_risk * 0.10
        + concept.visual_prompt_dependence_risk * 0.10
    )
    return concept.model_copy(update={
        "base_creative_score": round(base, 2),
        "total_penalty": round(penalty, 2),
        "overall_opportunity_score": round(max(0.0, base - penalty), 2),
    })


def _duplicate_reason(
    candidate: ProductConcept, selected: list[ProductConcept], threshold: float,
) -> str | None:
    for existing in selected:
        if candidate.product_name.casefold() == existing.product_name.casefold():
            return f"duplicate product name with {existing.concept_id}"
        signature = (candidate.silhouette_form.casefold(), candidate.construction_idea.casefold())
        other = (existing.silhouette_form.casefold(), existing.construction_idea.casefold())
        if signature == other:
            return f"duplicate silhouette/construction signature with {existing.concept_id}"
        similarity = _similarity(candidate, existing)
        if similarity >= threshold:
            return f"global semantic similarity {similarity:.3f} with {existing.concept_id}"
    return None


def _quality_failures(concept: ProductConcept, brief: CollectionBrief) -> list[str]:
    gates = brief.quality_gates
    failures: list[str] = []
    checks = (
        (concept.silhouette_distinctiveness_score, gates.minimum_silhouette_distinctiveness, "silhouette distinctiveness below minimum"),
        (concept.construction_novelty_score, gates.minimum_construction_novelty, "construction novelty below minimum"),
        (concept.manufacturability_score, gates.minimum_manufacturability, "manufacturability below minimum"),
    )
    failures.extend(message for value, minimum, message in checks if value < minimum)
    maximums = (
        (concept.iconic_product_resemblance_risk, gates.maximum_iconic_resemblance_risk, "iconic-product resemblance risk above maximum"),
        (concept.generic_mass_market_risk, gates.maximum_generic_mass_market_risk, "generic/mass-market risk above maximum"),
        (concept.gimmick_weak_use_case_risk, gates.maximum_gimmick_risk, "gimmick/weak-use-case risk above maximum"),
        (concept.visual_prompt_dependence_risk, gates.maximum_visual_prompt_dependence_risk, "visual-prompt dependence risk above maximum"),
    )
    failures.extend(message for value, maximum, message in maximums if value > maximum)
    if max(
        concept.silhouette_distinctiveness_score,
        concept.construction_novelty_score,
        concept.shape_recognizability_score,
    ) < gates.exceptional_creative_dimension:
        failures.append("no creative dimension reaches the exceptional threshold")
    return failures


def _diversity_failure(
    candidate: ProductConcept, counters: dict[str, Counter[str]],
    mechanism_counts: Counter[str], brief: CollectionBrief,
) -> str | None:
    rules = brief.diversity
    checks = (
        ("material", candidate.materials[0].casefold(), rules.maximum_primary_material_repetition),
        ("color", candidate.colors[0].casefold(), rules.maximum_primary_color_repetition),
        ("silhouette", candidate.silhouette_form.casefold(), rules.maximum_silhouette_repetition),
        ("construction", candidate.construction_idea.casefold(), rules.maximum_construction_repetition),
    )
    for kind, value, limit in checks:
        if counters[kind][value] >= limit:
            return f"collection {kind} repetition limit reached for {value!r}"
    mechanism_limits = {
        "transformable_modular": rules.maximum_transformable_modular,
        "folding": rules.maximum_folding_based,
        "expansion_volume_release": rules.maximum_expansion_volume_release,
        "asymmetry_led": rules.maximum_asymmetry_led,
    }
    for mechanism in candidate.conceptual_mechanisms:
        if mechanism_counts[mechanism] >= mechanism_limits[mechanism]:
            return f"conceptual mechanism limit reached for {mechanism!r}"
    return None


def generate_collection(
    brief: CollectionBrief,
    trends: list[SyntheticTrendSignal],
    candidates: list[ProductConcept],
    *,
    generated_at: datetime | None = None,
) -> GeneratedCollection:
    """Select a reproducible collection from explicitly synthetic candidates."""

    trend_by_id = {trend.signal_id: trend for trend in trends}
    if len(trend_by_id) != len(trends):
        raise CollectionGenerationError("trend signal IDs must be unique")
    concept_ids = [concept.concept_id for concept in candidates]
    if len(concept_ids) != len(set(concept_ids)):
        raise CollectionGenerationError("concept IDs must be unique")

    ranked: list[ProductConcept] = []
    rejected: dict[str, list[str]] = {}
    for candidate in candidates:
        trend = trend_by_id.get(candidate.trend_signal_id)
        if trend is None:
            raise CollectionGenerationError(f"unknown trend signal: {candidate.trend_signal_id}")
        if candidate.primary_trend != trend.signal or candidate.trend_score != trend.trend_score:
            raise CollectionGenerationError("concept trend label and score must match its source signal")
        failures = _quality_failures(candidate, brief)
        if failures:
            rejected[candidate.concept_id] = failures
        else:
            ranked.append(_rank(candidate, brief))

    ranked.sort(key=lambda item: (-float(item.overall_opportunity_score), item.concept_id))
    selected: list[ProductConcept] = []
    counters = {name: Counter() for name in ("material", "color", "silhouette", "construction")}
    mechanism_counts: Counter[str] = Counter()
    for category, quota in brief.quotas.by_category.items():
        chosen = 0
        for candidate in ranked:
            if candidate.category != category:
                continue
            duplicate_reason = _duplicate_reason(
                candidate, selected, brief.diversity.global_semantic_similarity
            )
            diversity_reason = _diversity_failure(
                candidate, counters, mechanism_counts, brief
            )
            if duplicate_reason or diversity_reason:
                rejected.setdefault(candidate.concept_id, []).append(
                    duplicate_reason or diversity_reason or "rejected"
                )
                continue
            selected.append(candidate)
            counters["material"][candidate.materials[0].casefold()] += 1
            counters["color"][candidate.colors[0].casefold()] += 1
            counters["silhouette"][candidate.silhouette_form.casefold()] += 1
            counters["construction"][candidate.construction_idea.casefold()] += 1
            mechanism_counts.update(candidate.conceptual_mechanisms)
            chosen += 1
            if chosen == quota:
                break
        if chosen != quota:
            raise CollectionGenerationError(
                f"category {category!r} supplied {chosen} diverse concepts for quota {quota}"
            )

    behaviors = {item.product_behavior.casefold() for item in selected}
    recognizable = sum(
        item.shape_recognizability_score >= brief.quality_gates.exceptional_creative_dimension
        for item in selected
    )
    construction_led = sum(item.construction_led for item in selected)
    minimum_failures = []
    if len(behaviors) < brief.diversity.minimum_distinct_product_behaviors:
        minimum_failures.append("distinct product behavior minimum")
    if recognizable < brief.diversity.minimum_silhouette_recognizable_concepts:
        minimum_failures.append("silhouette-recognizable concept minimum")
    if construction_led < brief.diversity.minimum_construction_led_concepts:
        minimum_failures.append("construction-led concept minimum")
    if minimum_failures:
        raise CollectionGenerationError(
            "collection failed conceptual diversity minimums: " + ", ".join(minimum_failures)
        )

    selected.sort(key=lambda item: (-float(item.overall_opportunity_score), item.concept_id))
    timestamp = generated_at or datetime.now(timezone.utc)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise CollectionGenerationError("generated_at must include a timezone")
    return GeneratedCollection(
        collection_id=brief.collection_id,
        brand_label=brief.brand_label,
        season=brief.season,
        concepts=selected,
        category_counts=dict(Counter(item.category for item in selected)),
        generated_at=timestamp,
        methodology_version=METHODOLOGY_VERSION,
        affiliation_disclaimer=brief.affiliation_disclaimer,
        limitations=[
            "All trend inputs, scores, rationales, and concepts are synthetic demonstration data.",
            "This output is not evidence of actual market demand, brand approval, or affiliation.",
        ],
        rejected_candidates=rejected,
        diversity_audit={
            "distinct_product_behaviors": len(behaviors),
            "silhouette_recognizable_concepts": recognizable,
            "construction_led_concepts": construction_led,
            "transformable_modular_concepts": mechanism_counts["transformable_modular"],
            "folding_based_concepts": mechanism_counts["folding"],
            "expansion_volume_release_concepts": mechanism_counts["expansion_volume_release"],
            "asymmetry_led_concepts": mechanism_counts["asymmetry_led"],
        },
    )
