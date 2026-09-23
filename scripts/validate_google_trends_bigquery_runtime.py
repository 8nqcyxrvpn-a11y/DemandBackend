"""Explicit one-shot runtime preflight; prints sanitized metadata only."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from app.market_intelligence.google_trends_runtime import GoogleTrendsRuntimePreflight


def main() -> int:
    result = GoogleTrendsRuntimePreflight().run()
    print(json.dumps(result.model_dump(mode="json"), sort_keys=True))
    return 0 if result.query_succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())
