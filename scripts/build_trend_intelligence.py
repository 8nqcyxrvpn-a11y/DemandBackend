#!/usr/bin/env python3
"""Print synthetic color trend rankings as JSON."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.config import DATASET_PATH
from app.trend_service import build_trend_signals


if __name__ == "__main__":
    print(json.dumps(build_trend_signals(DATASET_PATH), indent=2))

