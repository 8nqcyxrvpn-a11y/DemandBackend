# AI Fashion Intelligence Prototype

A production-shaped FastAPI prototype for exploring fashion trend signals, precomputed design opportunities, and dynamic demand estimates. All bundled figures and training rows are synthetic demo data. This project is not affiliated with Hermès, and no brand supplied the data.

## What is implemented

- `GET /collection` serves the precomputed five-product concept study at the JSON top level.
- `POST /predict-demand` dynamically runs a `RandomForestRegressor`, then adds 15% safety stock.
- `GET /trend-signals` computes transparent percentile-ranked color signals from the synthetic CSV and explicitly returns `is_live_data: false`.
- `GET /model-info`, `/health`, and `/` expose model metadata and service status.
- Pydantic contracts reserve a clean shape for future live trend signals and brand profiles.

The collection endpoint is static by design. Its product demand and concept scores are not recalculated. Image prompts are preserved as text only; this repository does not generate images.

## Architecture

```text
Synthetic CSV ──> trend_service ──> /trend-signals
      │
      └──> training script ──> demand_model.joblib ──> demand_service ──> /predict-demand

final_ai_collection.json ──> collection_service ──> /collection
```

The intended future system is:

```text
External ingestion → normalization → deduplication → source-quality weighting
→ momentum, velocity, breadth and category relevance → brand fit
→ whitespace analysis → opportunity score → concept generation
→ demand forecast → inventory recommendation → evidence and confidence
```

No external ingestion or factual Hermès brand intelligence is fabricated here. A future whitespace engine should compare a normalized trend signal, brand DNA, current assortment, and existing product territory.

## Install and run locally

The deployed runtime is pinned to Python 3.13.7 in `.python-version`.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/train_demand_model.py
python scripts/validate_artifacts.py
uvicorn server:app --reload
```

The existing model artifact is deployed with the application and loaded using the pinned scikit-learn version. To rebuild it intentionally from the synthetic training data, run `python scripts/train_demand_model.py`; the Render build does not retrain or overwrite it.

Test a dynamic prediction:

```bash
curl -X POST http://localhost:8000/predict-demand \
  -H "Content-Type: application/json" \
  -d '{
    "price_usd": 4200,
    "trend_mentions": 780,
    "trend_growth_pct": 60,
    "inventory_units": 950
  }'
```

Run tests:

```bash
pytest -q
```

Build trend intelligence directly:

```bash
python scripts/build_trend_intelligence.py
```

## API contracts

`POST /predict-demand` accepts, in model feature order:

1. `price_usd`
2. `trend_mentions`
3. `trend_growth_pct`
4. `inventory_units`

Its stable frontend fields are:

```text
forecast.predicted_demand_units
forecast.safety_stock_units
forecast.recommended_inventory_units
```

Invalid or missing input receives FastAPI's normal `422` response. Missing runtime artifacts receive a controlled `503` without exposing paths or tracebacks to clients.

## Render deployment

The included `render.yaml` installs binary dependency wheels, validates the existing model and data artifacts, and starts the service. The exact start command is:

```bash
uvicorn server:app --host 0.0.0.0 --port $PORT
```

Prototype CORS defaults to all origins with credentials disabled. Tighten it by setting `CORS_ORIGINS` to a comma-separated list of frontend origins.

## Model and data limitations

The 300-row dataset is deterministic synthetic demo data created for this reconstruction. It is not the unavailable original dataset, so its metrics and predictions are not expected to reproduce the historical approximate values in the brief. The training script reports random-split and chronological-split MAE, R², and MAPE, then fits the deployable model on all rows.

`inventory_units` remains a feature for frontend compatibility. In real data this can introduce demand censoring or leakage because observed sales may be constrained by available stock. A production model should distinguish latent demand, observed sales, stock availability, stockouts, and lead time.

Random forests also do not extrapolate reliably beyond training ranges. Production work should add range validation, out-of-distribution warnings, and calibrated confidence indicators.

The current trend score is descriptive ranking, not future forecasting. A true trend model should use lagged mentions and growth, rolling averages and volatility, source breadth, category momentum, seasonality, and a time index to predict next-period growth or future interest.
