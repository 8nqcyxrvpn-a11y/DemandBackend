"""Temporary, opt-in HTTP transport for the one-shot BigQuery preflight."""

from __future__ import annotations

import os
import secrets
from typing import Callable

from fastapi import FastAPI, Header, HTTPException

from app.market_intelligence.google_trends_runtime import (
    GoogleTrendsPreflightResult,
    GoogleTrendsRuntimePreflight,
)

ENABLE_ENV = "ENABLE_GOOGLE_TRENDS_PREFLIGHT"
SECRET_ENV = "GOOGLE_TRENDS_PREFLIGHT_SECRET"
SECRET_HEADER = "X-Google-Trends-Preflight-Secret"
MINIMUM_SECRET_LENGTH = 32
ROUTE = "/internal/preflight/google-trends-bigquery"


def _is_enabled() -> bool:
    return os.getenv(ENABLE_ENV, "").strip().casefold() == "true"


def register_google_trends_preflight_route(
    app: FastAPI,
    *,
    runtime_factory: Callable[[], GoogleTrendsRuntimePreflight] = GoogleTrendsRuntimePreflight,
) -> bool:
    """Register the hidden route only when explicitly enabled at process startup."""
    if not _is_enabled():
        return False

    @app.post(ROUTE, include_in_schema=False, response_model=GoogleTrendsPreflightResult)
    def google_trends_bigquery_preflight(
        supplied_secret: str | None = Header(default=None, alias=SECRET_HEADER),
    ) -> GoogleTrendsPreflightResult:
        expected_secret = os.getenv(SECRET_ENV, "")
        if len(expected_secret) < MINIMUM_SECRET_LENGTH:
            raise HTTPException(status_code=503, detail="Preflight is not securely configured.")
        if supplied_secret is None or not secrets.compare_digest(supplied_secret, expected_secret):
            # Deliberately indistinguishable from an unknown private route.
            raise HTTPException(status_code=404, detail="Not Found")
        return runtime_factory().run()

    return True
