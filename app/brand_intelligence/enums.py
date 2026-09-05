"""Controlled values shared by the brand-intelligence domain."""

from __future__ import annotations

from enum import Enum


class StringEnum(str, Enum):
    """Python 3.9-compatible string enum."""


class EvidenceStatus(StringEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class ReviewStatus(StringEnum):
    CANDIDATE = "candidate"
    REVIEWED = "reviewed"
    APPROVED = "approved"
    REJECTED = "rejected"


class SourceType(StringEnum):
    PRODUCT_PAGE = "product_page"
    COLLECTION_PAGE = "collection_page"
    INSTITUTIONAL_PAGE = "institutional_page"
    PRESS_RELEASE = "press_release"
    EDITORIAL = "editorial"
    ARCHIVE = "archive"
    OTHER = "other"


class CaptureMethod(StringEnum):
    MANUAL = "manual"
    API = "api"
    AUTHORIZED_FETCH = "authorized_fetch"
    IMPORT = "import"


class AvailabilityStatus(StringEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    ARCHIVAL = "archival"
    UNKNOWN = "unknown"


class SeasonType(StringEnum):
    SPRING_SUMMER = "spring_summer"
    FALL_WINTER = "fall_winter"
    RESORT = "resort"
    PRE_FALL = "pre_fall"
    CAPSULE = "capsule"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"


class AttributeType(StringEnum):
    COLOR = "color"
    MATERIAL = "material"
    SILHOUETTE_FORM = "silhouette_form"
    CRAFTSMANSHIP_CONSTRUCTION = "craftsmanship_construction"


class TraitType(StringEnum):
    BRAND_VALUE = "brand_value"
    COLOR_LANGUAGE = "color_language"
    MATERIAL_LANGUAGE = "material_language"
    SILHOUETTE_LANGUAGE = "silhouette_language"
    CRAFTSMANSHIP_CODE = "craftsmanship_code"
    CATEGORY_TERRITORY = "category_territory"
    PRICE_POSITIONING = "price_positioning"


class TerritoryStatus(StringEnum):
    CORE = "core"
    RECURRING = "recurring"
    OCCASIONAL = "occasional"
    EMERGING = "emerging"
    UNKNOWN = "unknown"


class PriceType(StringEnum):
    RETAIL = "retail"
    STARTING_AT = "starting_at"
    RANGE = "range"
    UNKNOWN = "unknown"

