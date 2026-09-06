"""Reviewed synthetic fixtures for exercising collection architecture only."""

from __future__ import annotations

from app.collection_intelligence.models import (
    CollectionBrief,
    CollectionQuotas,
    ProductConcept,
    SyntheticTrendSignal,
)


DEMO_TRENDS = [
    SyntheticTrendSignal(signal_id="demo-deconstruction", signal="Deconstructed Tailoring", signal_type="construction", trend_score=88),
    SyntheticTrendSignal(signal_id="demo-blue", signal="Electric Blue", signal_type="color", trend_score=82),
    SyntheticTrendSignal(signal_id="demo-narrow", signal="Narrow Silhouettes", signal_type="silhouette_form", trend_score=81),
    SyntheticTrendSignal(signal_id="demo-volume", signal="Selective Volume", signal_type="silhouette_form", trend_score=75),
    SyntheticTrendSignal(signal_id="demo-yellow", signal="Butter Yellow", signal_type="color", trend_score=78),
]

DEMO_BRIEF = CollectionBrief(
    collection_id="fictional-hermes-seasonal-options-v1",
    brand_label="Hermès — fictional concept study",
    season="Synthetic seasonal demonstration",
    quotas=CollectionQuotas(by_category={
        "Outerwear": 3,
        "Bag": 3,
        "Small Leather Good": 2,
        "Footwear": 3,
        "Ready-to-Wear": 3,
        "Belt / Accessory": 2,
        "Scarf": 1,
        "Jewelry": 1,
    }),
    affiliation_disclaimer="Independent fictional concept study; not affiliated with or endorsed by Hermès.",
)

# Scores are manually reviewed synthetic rubric inputs in this order:
# silhouette, construction, recognizability, manufacturability,
# generic risk, iconic resemblance risk, gimmick risk, prompt-dependence risk.
_QUALITY = {
    "ow-01": (84, 82, 80, 76, 24, 25, 18, 16),
    "ow-02": (88, 86, 84, 72, 20, 22, 25, 14),
    "ow-03": (86, 84, 81, 68, 24, 25, 28, 18),
    "bag-01": (90, 84, 88, 70, 18, 32, 24, 12),
    "bag-02": (87, 91, 85, 64, 16, 28, 30, 14),
    "bag-03": (91, 85, 90, 67, 14, 34, 28, 10),
    "slg-01": (79, 88, 82, 74, 22, 18, 16, 20),
    "slg-02": (76, 84, 78, 73, 25, 20, 18, 22),
    "fw-01": (84, 82, 83, 69, 24, 30, 22, 16),
    "fw-02": (82, 80, 79, 78, 28, 38, 12, 18),
    "fw-03": (86, 85, 84, 68, 20, 32, 24, 14),
    "rtw-01": (88, 83, 86, 66, 18, 24, 26, 12),
    "rtw-02": (83, 87, 80, 72, 22, 20, 18, 18),
    "rtw-03": (85, 82, 82, 70, 24, 18, 20, 16),
    "acc-01": (78, 84, 77, 75, 28, 22, 18, 22),
    "acc-02": (82, 80, 79, 73, 24, 20, 16, 20),
    "wild-01": (85, 89, 83, 63, 16, 18, 30, 14),
    "wild-02": (84, 91, 86, 62, 18, 24, 28, 12),
    "reject-layer-wallet": (48, 55, 42, 84, 78, 35, 25, 64),
    "reject-needle-boot": (54, 52, 48, 86, 82, 44, 18, 58),
    "reject-soft-belt": (58, 61, 50, 51, 62, 25, 84, 72),
}

_BEHAVIOR = {
    "ow-01": "closure redirects collar line", "ow-02": "panel pivots into weather cover",
    "ow-03": "volume migrates rearward", "bag-01": "capacity expands on an arc",
    "bag-02": "frame compacts the bag", "bag-03": "pouch suspends under tension",
    "slg-01": "cards fan from a tension spine", "slg-02": "nested shells release by flexion",
    "fw-01": "structural line tensions the upper", "fw-02": "vamp planes flex independently",
    "fw-03": "sole line becomes rear strap", "rtw-01": "layers separate in motion",
    "rtw-02": "fastening redistributes jacket volume", "rtw-03": "offset panel orbits in motion",
    "acc-01": "articulated strap redirects waist line", "acc-02": "weighted ends self-balance",
    "wild-01": "pleats collapse from volume to flat", "wild-02": "links articulate without hinges",
    "reject-layer-wallet": "flaps open", "reject-needle-boot": "standard boot flexes",
    "reject-soft-belt": "padding inflates",
}

_MECHANISMS = {
    "ow-01": ["asymmetry_led"], "ow-02": ["transformable_modular"],
    "ow-03": ["expansion_volume_release"], "bag-01": ["expansion_volume_release"],
    "bag-02": ["transformable_modular", "folding"], "bag-03": [],
    "slg-01": [], "slg-02": [], "fw-01": [], "fw-02": [], "fw-03": ["asymmetry_led"],
    "rtw-01": [], "rtw-02": ["transformable_modular"], "rtw-03": [],
    "acc-01": [], "acc-02": [], "wild-01": ["folding"], "wild-02": [],
    "reject-layer-wallet": ["folding"], "reject-needle-boot": [],
    "reject-soft-belt": ["expansion_volume_release"],
}


def _concept(
    concept_id: str, name: str, category: str, idea: str, innovation: str,
    whitespace: str, materials: list[str], colors: list[str], silhouette: str,
    construction: str, trend_id: str, trend: str, trend_score: float,
    originality: float, fit: float, commercial: float,
) -> ProductConcept:
    quality = _QUALITY[concept_id]
    return ProductConcept(
        concept_id=concept_id,
        product_name=name,
        category=category,
        core_idea=idea,
        innovation=innovation,
        whitespace_rationale=whitespace,
        materials=materials,
        colors=colors,
        silhouette_form=silhouette,
        construction_idea=construction,
        primary_trend=trend,
        trend_signal_id=trend_id,
        trend_score=trend_score,
        originality_score=originality,
        brand_fit_score=fit,
        brand_coherence_score=fit,
        commercial_potential_score=commercial,
        silhouette_distinctiveness_score=quality[0],
        construction_novelty_score=quality[1],
        shape_recognizability_score=quality[2],
        manufacturability_score=quality[3],
        generic_mass_market_risk=quality[4],
        iconic_product_resemblance_risk=quality[5],
        gimmick_weak_use_case_risk=quality[6],
        visual_prompt_dependence_risk=quality[7],
        product_behavior=_BEHAVIOR[concept_id],
        conceptual_mechanisms=_MECHANISMS[concept_id],
        construction_led=quality[1] >= 80,
        image_prompt=(
            f"Independent fictional luxury concept study: {name}, {idea.lower()}, "
            f"in {colors[0]} {materials[0]}; physically plausible construction, no logos, "
            "monograms, trademarks, or text; not an official Hermès product."
        ),
    )


DEMO_CANDIDATES = [
    _concept("ow-01", "Meridian Collar Coat", "Outerwear", "A continuous displaced line travels from collar through lapel and closure around the body.", "One curved structural seam produces distinct front, side, and rear readings.", "Avoids literal half-and-half deconstruction while making tailoring legible from shape.", ["cashmere blend", "silk lining"], ["camel", "electric blue"], "wrapped column", "continuous meridian seam", "demo-deconstruction", "Deconstructed Tailoring", 88, 90, 91, 86),
    _concept("ow-02", "Pivot Trench", "Outerwear", "A trench whose back panel pivots into a protective shoulder cape.", "A concealed leather hinge changes coverage without detachable parts.", "Adds adaptable volume to a practical coat archetype.", ["cotton gabardine", "calfskin"], ["olive green", "natural tan"], "a-line trench", "pivot panel", "demo-volume", "Selective Volume", 75, 92, 87, 88),
    _concept("ow-03", "Migrating Volume Coat", "Outerwear", "Internal folds hold volume at the back when closed and redistribute it around the body when opened.", "Connected internal channels move fullness without ordinary side gussets.", "Creates two related silhouettes through pattern engineering rather than add-on panels.", ["double-face wool", "goatskin"], ["burgundy", "charcoal"], "rear-volume cocoon", "migrating internal fold", "demo-volume", "Selective Volume", 75, 91, 88, 82),
    _concept("bag-01", "Arc Volume", "Bag", "A compressed base supports an expandable curved upper body.", "Controlled expansion changes capacity and profile.", "Creates volume language without adapting an existing icon.", ["calfskin", "suede"], ["electric blue", "black"], "arched", "expandable shell", "demo-blue", "Electric Blue", 82, 94, 88, 92),
    _concept("bag-02", "Fold Frame", "Bag", "A rigid-soft bag folds inward from its external frame.", "The structural perimeter transforms the body from geometric to compact.", "Uses movement and geometry as identity.", ["box leather", "lambskin"], ["chocolate brown", "graphite"], "geometric", "folding frame", "demo-deconstruction", "Deconstructed Tailoring", 88, 95, 86, 87),
    _concept("bag-03", "Suspended Pouch", "Bag", "A soft pouch hangs independently inside a sculptural handle.", "Carrying structure and storage body are visibly separated.", "Explores a new relationship between handle and body.", ["suede", "lacquered metal"], ["butter yellow", "cream"], "suspended pouch", "tension suspension", "demo-yellow", "Butter Yellow", 78, 92, 84, 85),
    _concept("slg-01", "Tension Spine Wallet", "Small Leather Good", "A slim internal leather spine fans cards outward when flexed.", "Leather tension creates access without stacked flaps or mechanical hardware.", "Makes the closed edge and opening behavior recognizable through craft.", ["goatskin", "calfskin"], ["electric blue", "tan"], "spined wedge", "tensioned leather spine", "demo-deconstruction", "Deconstructed Tailoring", 88, 92, 89, 84),
    _concept("slg-02", "Compression Nest Case", "Small Leather Good", "Two leather shells nest into a single compact card case.", "Folded edges release through calibrated leather flex instead of a metal rail.", "Turns material compression into a durable interaction.", ["box calf", "goatskin"], ["burgundy", "navy"], "nested lozenge", "compression-fit shells", "demo-narrow", "Narrow Silhouettes", 81, 90, 87, 85),
    _concept("fw-01", "Tension Trace Boot", "Footwear", "A structural leather line begins beneath the heel and tensions the upper toward the vamp.", "The continuous load-bearing trace stabilizes a narrow profile.", "Creates a recognizable side elevation through functional construction.", ["polished calfskin", "leather sole"], ["black", "dark brown"], "tensioned ankle boot", "underfoot tension trace", "demo-narrow", "Narrow Silhouettes", 81, 91, 90, 84),
    _concept("fw-02", "Split Vamp Loafer", "Footwear", "Overlapping planes replace the conventional apron seam.", "A layered vamp preserves flexibility and a slim last.", "Reconstructs a familiar shoe while retaining wearability.", ["glazed calfskin", "leather sole"], ["chocolate brown", "cream"], "slim loafer", "layered vamp", "demo-deconstruction", "Deconstructed Tailoring", 88, 87, 94, 93),
    _concept("fw-03", "Soleline Slingback", "Footwear", "A structural line begins under the sole, rises around the foot, and becomes the rear strap.", "One load-bearing nappa element joins sole support and slingback tension.", "Makes the profile identifiable through a functional continuous gesture.", ["nappa leather", "leather sole"], ["butter yellow", "black"], "rising-line slingback", "sole-to-strap structure", "demo-yellow", "Butter Yellow", 78, 92, 87, 83),
    _concept("rtw-01", "Floating Seam Dress", "Ready-to-Wear", "Layered panels appear to float around a narrow column.", "Interrupted seams separate structural and fluid layers.", "Combines architecture and movement without ornament.", ["silk crepe", "organza"], ["ivory", "black"], "column dress", "interrupted seam", "demo-narrow", "Narrow Silhouettes", 81, 93, 86, 84),
    _concept("rtw-02", "Orbit Seam Jacket", "Ready-to-Wear", "A continuous curved seam redistributes jacket volume when one fastening point moves.", "The same panels shift proportion without detachable components.", "Creates adaptable tailoring without resembling technical modular apparel.", ["fine wool", "silk twill"], ["navy blue", "cream"], "orbit-waist jacket", "redirected curved seam", "demo-deconstruction", "Deconstructed Tailoring", 88, 92, 88, 84),
    _concept("rtw-03", "Orbit Panel Skirt", "Ready-to-Wear", "An offset weighted panel appears to travel around the body in motion.", "Pattern cutting and weight distribution change front and side readings.", "Makes movement structurally visible rather than relying on subtle grain direction.", ["satin", "wool crepe"], ["burgundy", "powder pink"], "orbiting midi", "weighted offset panel", "demo-deconstruction", "Deconstructed Tailoring", 88, 91, 86, 85),
    _concept("acc-01", "Articulated Wrap Belt", "Belt / Accessory", "An articulated leather section redirects how the strap frames the waist.", "Flexible joined segments permit multiple crossing paths without reversibility hardware.", "Changes styling behavior and waist silhouette rather than only color.", ["soft calfskin", "flexible core"], ["cream", "dark brown"], "redirected wrap belt", "articulated strap", "demo-volume", "Selective Volume", 75, 90, 88, 84),
    _concept("acc-02", "Counterweight Wrap Belt", "Belt / Accessory", "Differently weighted leather ends balance around a concealed waist anchor.", "Material weight holds an asymmetric wrap without a conventional visible buckle.", "Creates useful styling variation without padding or inflation.", ["bridle leather", "brushed metal"], ["electric blue", "natural tan"], "counterbalanced wrap", "concealed weighted anchor", "demo-blue", "Electric Blue", 82, 91, 89, 82),
    _concept("wild-01", "Kinetic Fold Scarf", "Scarf", "Engineered folds give a silk scarf quiet three-dimensional movement.", "Heat-set pleats collapse fully for conventional wear.", "Extends selective volume into a lightweight textile object.", ["silk twill", "silk organza"], ["powder pink", "electric blue"], "fluid square", "engineered pleat", "demo-volume", "Selective Volume", 75, 93, 90, 86),
    _concept("wild-02", "Leather Link Cuff", "Jewelry", "Small leather links articulate around the wrist.", "Interlocking units flex without a conventional hinge.", "Applies construction-led modularity to jewelry.", ["barenia-style calfskin", "precious-metal-free alloy"], ["olive green", "natural tan"], "articulated cuff", "interlocking links", "demo-deconstruction", "Deconstructed Tailoring", 88, 94, 86, 84),
    _concept("reject-layer-wallet", "Layer Wallet", "Small Leather Good", "Overlapping leather planes open as a conventional wallet.", "Multiple flaps provide access.", "Changes arrangement but lacks a recognizable new object behavior.", ["calfskin"], ["electric blue"], "flat rectangle", "stacked flaps", "demo-deconstruction", "Deconstructed Tailoring", 88, 58, 88, 90),
    _concept("reject-needle-boot", "Needle Line Boot", "Footwear", "A pointed ankle boot uses a displaced decorative seam.", "An elongated last changes proportion.", "Relies on familiar fashion styling rather than construction whitespace.", ["calfskin"], ["black"], "pointed ankle boot", "decorative offset seam", "demo-narrow", "Narrow Silhouettes", 81, 60, 90, 92),
    _concept("reject-soft-belt", "Soft Form Belt", "Belt / Accessory", "A padded section inflates around the waist.", "Internal padding creates temporary volume.", "Volume is mainly visual and has a weak functional use case.", ["soft calfskin"], ["cream"], "inflated belt", "padded chamber", "demo-volume", "Selective Volume", 75, 70, 86, 78),
]
