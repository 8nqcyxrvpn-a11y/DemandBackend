"""Load versioned brand-evidence datasets without coupling them to the API."""

from __future__ import annotations

from pathlib import Path

from app.brand_intelligence.models import BrandEvidenceDataset


def load_evidence_dataset(path: str | Path) -> BrandEvidenceDataset:
    return BrandEvidenceDataset.model_validate_json(Path(path).read_text(encoding="utf-8"))
