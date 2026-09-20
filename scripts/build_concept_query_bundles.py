"""Create the immutable initial query and linkage artifacts; refuses overwrite."""

from pathlib import Path
import sys
import hashlib

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.demand_intelligence import (
    build_candidate_artifacts,
    build_reviewed_linkage_artifact,
    persist_immutable_artifact,
)


def main() -> None:
    bundles, linkages = build_candidate_artifacts()
    persist_immutable_artifact(
        Path("data/market_evidence/concept_query_bundles/creative_refinement_v2_query_bundles_v1.json"), bundles
    )
    persist_immutable_artifact(
        Path("data/market_evidence/concept_signal_linkages/creative_refinement_v2_signal_linkages_v1.json"), linkages
    )


def review() -> None:
    bundles, linkages = build_candidate_artifacts()
    v1_path = Path("data/market_evidence/concept_signal_linkages/creative_refinement_v2_signal_linkages_v1.json")
    reviewed = build_reviewed_linkage_artifact(
        bundles, linkages, hashlib.sha256(v1_path.read_bytes()).hexdigest()
    )
    persist_immutable_artifact(
        Path("data/market_evidence/concept_signal_linkages/creative_refinement_v2_signal_linkages_v2.json"), reviewed
    )


if __name__ == "__main__":
    review()
