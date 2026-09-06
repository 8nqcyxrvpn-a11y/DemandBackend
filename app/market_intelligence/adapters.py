"""Provider port. Concrete adapters require documented, authorized source access."""

from __future__ import annotations

from typing import Protocol

from app.market_intelligence.models import MarketObservation, MarketSource


class MarketSourceAdapter(Protocol):
    @property
    def source(self) -> MarketSource: ...

    def retrieve(self) -> list[MarketObservation]: ...
