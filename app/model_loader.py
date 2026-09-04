"""Cached model loading with controlled artifact errors."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib


class ArtifactError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def load_model(path: Path) -> Any:
    if not path.is_file():
        raise ArtifactError("Demand model artifact is unavailable.")
    try:
        model = joblib.load(path)
    except Exception as exc:
        raise ArtifactError("Demand model artifact could not be loaded.") from exc
    if not hasattr(model, "predict"):
        raise ArtifactError("Demand model artifact is invalid.")
    return model

