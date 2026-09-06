from collections import Counter
from datetime import datetime, timezone

import pytest

from app.collection_intelligence.demo import DEMO_BRIEF, DEMO_CANDIDATES, DEMO_TRENDS
from app.collection_intelligence.models import ProductConcept
from app.collection_intelligence.service import CollectionGenerationError, generate_collection


NOW = datetime(2026, 9, 7, tzinfo=timezone.utc)


def test_generates_eighteen_ranked_concepts_at_exact_category_quotas():
    result = generate_collection(DEMO_BRIEF, DEMO_TRENDS, DEMO_CANDIDATES, generated_at=NOW)

    assert len(result.concepts) == 18
    assert result.category_counts == DEMO_BRIEF.quotas.by_category
    assert [item.overall_opportunity_score for item in result.concepts] == sorted(
        (item.overall_opportunity_score for item in result.concepts), reverse=True
    )
    assert result.is_synthetic is True
    assert "not affiliated" in result.affiliation_disclaimer.lower()
    assert all(item.is_synthetic and item.data_source == "synthetic_demo" for item in result.concepts)
    assert result.rejected_candidates == {
        "reject-layer-wallet": [
            "silhouette distinctiveness below minimum",
            "construction novelty below minimum",
            "generic/mass-market risk above maximum",
            "no creative dimension reaches the exceptional threshold",
        ],
        "reject-needle-boot": [
            "silhouette distinctiveness below minimum",
            "construction novelty below minimum",
            "generic/mass-market risk above maximum",
            "no creative dimension reaches the exceptional threshold",
        ],
        "reject-soft-belt": [
            "silhouette distinctiveness below minimum",
            "manufacturability below minimum",
            "gimmick/weak-use-case risk above maximum",
            "visual-prompt dependence risk above maximum",
            "no creative dimension reaches the exceptional threshold",
        ],
    }


def test_output_is_reproducible_and_trend_scores_resolve_to_synthetic_inputs():
    first = generate_collection(DEMO_BRIEF, DEMO_TRENDS, DEMO_CANDIDATES, generated_at=NOW)
    second = generate_collection(DEMO_BRIEF, DEMO_TRENDS, list(reversed(DEMO_CANDIDATES)), generated_at=NOW)

    assert first == second
    trends = {item.signal_id: item for item in DEMO_TRENDS}
    assert all(
        item.primary_trend == trends[item.trend_signal_id].signal
        and item.trend_score == trends[item.trend_signal_id].trend_score
        for item in first.concepts
    )


def test_diversity_limits_are_enforced_collection_wide():
    result = generate_collection(DEMO_BRIEF, DEMO_TRENDS, DEMO_CANDIDATES, generated_at=NOW)
    rules = DEMO_BRIEF.diversity

    assert max(Counter(x.materials[0].casefold() for x in result.concepts).values()) <= rules.maximum_primary_material_repetition
    assert max(Counter(x.colors[0].casefold() for x in result.concepts).values()) <= rules.maximum_primary_color_repetition
    assert max(Counter(x.silhouette_form.casefold() for x in result.concepts).values()) <= rules.maximum_silhouette_repetition
    assert max(Counter(x.construction_idea.casefold() for x in result.concepts).values()) <= rules.maximum_construction_repetition
    assert result.diversity_audit["transformable_modular_concepts"] <= rules.maximum_transformable_modular
    assert result.diversity_audit["folding_based_concepts"] <= rules.maximum_folding_based
    assert result.diversity_audit["expansion_volume_release_concepts"] <= rules.maximum_expansion_volume_release
    assert result.diversity_audit["asymmetry_led_concepts"] <= rules.maximum_asymmetry_led
    assert result.diversity_audit["distinct_product_behaviors"] >= rules.minimum_distinct_product_behaviors
    assert result.diversity_audit["silhouette_recognizable_concepts"] >= rules.minimum_silhouette_recognizable_concepts
    assert result.diversity_audit["construction_led_concepts"] >= rules.minimum_construction_led_concepts


def test_revised_weights_and_risk_penalties_are_applied_exactly():
    result = generate_collection(DEMO_BRIEF, DEMO_TRENDS, DEMO_CANDIDATES, generated_at=NOW)
    concept = next(item for item in result.concepts if item.concept_id == "bag-01")

    expected_base = (
        concept.commercial_potential_score * 0.15
        + concept.originality_score * 0.15
        + concept.brand_coherence_score * 0.15
        + concept.trend_score * 0.10
        + concept.silhouette_distinctiveness_score * 0.15
        + concept.construction_novelty_score * 0.15
        + concept.shape_recognizability_score * 0.10
        + concept.manufacturability_score * 0.05
    )
    expected_penalty = (
        concept.generic_mass_market_risk * 0.15
        + concept.iconic_product_resemblance_risk * 0.20
        + concept.gimmick_weak_use_case_risk * 0.10
        + concept.visual_prompt_dependence_risk * 0.10
    )
    assert concept.base_creative_score == round(expected_base, 2)
    assert concept.total_penalty == round(expected_penalty, 2)
    assert concept.overall_opportunity_score == round(expected_base - expected_penalty, 2)


def test_near_duplicate_in_same_category_cannot_fill_a_quota():
    base = DEMO_CANDIDATES[0]
    duplicate = base.model_copy(update={
        "concept_id": "ow-copy",
        "product_name": "Splitline Coat Variation",
        "originality_score": 100,
        "core_idea": base.core_idea + " slight variation",
    })
    candidates = [item for item in DEMO_CANDIDATES if item.category != "Outerwear"] + [base, duplicate]

    with pytest.raises(CollectionGenerationError, match="Outerwear"):
        generate_collection(DEMO_BRIEF, DEMO_TRENDS, candidates, generated_at=NOW)


def test_semantic_similarity_is_global_across_categories():
    source = DEMO_CANDIDATES[0]
    clones = []
    for index in range(3):
        clones.append(source.model_copy(update={
            "concept_id": f"global-clone-{index}",
            "product_name": f"Global Clone {index}",
            "category": "Bag",
            "silhouette_form": f"clone silhouette {index}",
            "construction_idea": f"clone construction {index}",
        }))
    candidates = [item for item in DEMO_CANDIDATES if item.category != "Bag"] + clones

    with pytest.raises(CollectionGenerationError, match="Bag"):
        generate_collection(DEMO_BRIEF, DEMO_TRENDS, candidates, generated_at=NOW)


def test_conceptual_mechanism_maximum_can_prevent_quota_filling():
    candidates = [
        item.model_copy(update={"conceptual_mechanisms": ["transformable_modular"]})
        if item.category == "Bag" else item
        for item in DEMO_CANDIDATES
    ]

    with pytest.raises(CollectionGenerationError, match="Bag"):
        generate_collection(DEMO_BRIEF, DEMO_TRENDS, candidates, generated_at=NOW)


def test_collection_minimum_distinct_behaviors_is_enforced():
    candidates = [item.model_copy(update={"product_behavior": "same behavior"}) for item in DEMO_CANDIDATES]

    with pytest.raises(CollectionGenerationError, match="distinct product behavior"):
        generate_collection(DEMO_BRIEF, DEMO_TRENDS, candidates, generated_at=NOW)


def test_unknown_or_mutated_trend_evidence_is_rejected():
    changed = DEMO_CANDIDATES[0].model_copy(update={"trend_score": 99})
    candidates = [changed, *DEMO_CANDIDATES[1:]]

    with pytest.raises(CollectionGenerationError, match="trend label and score"):
        generate_collection(DEMO_BRIEF, DEMO_TRENDS, candidates, generated_at=NOW)


def test_required_concept_contract_rejects_empty_design_attributes():
    payload = DEMO_CANDIDATES[0].model_dump()
    payload["materials"] = []

    with pytest.raises(ValueError):
        ProductConcept.model_validate(payload)
