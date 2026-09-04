"""Public API and future-pipeline data contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class DemandInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    price_usd: float = Field(ge=0, description="Retail price in US dollars.")
    trend_mentions: float = Field(ge=0, description="Observed trend mention volume.")
    trend_growth_pct: float
    inventory_units: float = Field(ge=0, description="Currently available inventory.")


class TrendSignal(BaseModel):
    """Normalized contract for future real signal ingestion; no live data is implied."""

    date: datetime
    signal: str
    signal_type: str
    source: str
    region: str
    interest_score: float
    growth_pct: float
    evidence_url: Optional[str] = None


class BrandProfile(BaseModel):
    """Placeholder contract for a future brand-DNA and whitespace engine."""

    brand_name: str
    brand_values: list[str] = Field(default_factory=list)
    silhouette_language: list[str] = Field(default_factory=list)
    material_language: list[str] = Field(default_factory=list)
    color_language: list[str] = Field(default_factory=list)
    craftsmanship_codes: list[str] = Field(default_factory=list)
    price_positioning: Optional[str] = None
    current_categories: list[str] = Field(default_factory=list)
    known_existing_product_territory: list[str] = Field(default_factory=list)
    restricted_iconic_shapes: list[str] = Field(default_factory=list)
    target_customer: Optional[str] = None
    commercial_constraints: list[str] = Field(default_factory=list)
