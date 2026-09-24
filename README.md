# AI Fashion Intelligence Prototype

A production-shaped FastAPI prototype for exploring fashion trend signals, precomputed design opportunities, and dynamic demand estimates. All bundled figures and training rows are synthetic demo data. This project is not affiliated with Hermès, and no brand supplied the data.

## What is implemented

- `GET /collection` serves the precomputed five-product concept study at the JSON top level.
- `POST /predict-demand` dynamically runs a `RandomForestRegressor`, then adds 15% safety stock.
- `GET /trend-signals` computes transparent percentile-ranked color signals from the synthetic CSV and explicitly returns `is_live_data: false`.
- `GET /market-intelligence/google-trends` retrieves real factual observations from the official Google Trends BigQuery public dataset. Raw terms remain unresolved unless an explicit reviewed taxonomy rule matches them.
- `GET /model-info`, `/health`, and `/` expose model metadata and service status.
- Pydantic contracts reserve a clean shape for future live trend signals and brand profiles.

The collection endpoint is static by design. Its product demand and concept scores are not recalculated. Image prompts are preserved as text only; this repository does not generate images.

## Architecture

```text
Synthetic CSV ──> trend_service ──> /trend-signals
      │
      └──> training script ──> demand_model.joblib ──> demand_service ──> /predict-demand

final_ai_collection.json ──> collection_service ──> /collection

Google Trends BigQuery
        ↓
GoogleTrendsBigQueryAdapter
        ↓
MarketObservation (real factual evidence)
        ↓
explicit taxonomy normalization
        ↓
derived market metrics only when evidence requirements are satisfied

Synthetic training data
        ↓
RandomForest demand model
        ↓
/predict-demand
```

The real Google Trends evidence path and synthetic demand model are deliberately separate. Google Trends terms are not sent to `/predict-demand`, and public attention is not treated as sales demand. The temporal-metrics layer continues to require at least three periods and two independent real sources before reporting sufficient evidence; Google Trends alone cannot satisfy source breadth.

### Production fashion taxonomy

Google Trends normalization uses the versioned `fashion-taxonomy-1.0` artifact at `data/taxonomies/fashion/fashion_taxonomy_v1.json`. Its approved categories are colors, materials, garments, footwear, bags/accessories, silhouettes, patterns, and fashion aesthetics/styles. Mapping is limited to case-insensitive, whitespace-normalized exact aliases in that artifact; substring matching, fuzzy matching, and model-generated semantic guesses are not used.

The live endpoint returns all factual observations separately from resolved fashion signals, unresolved observations, and ambiguous observations. It also reports the raw, resolved, unresolved, and ambiguous counts plus the taxonomy artifact SHA-256. A lexical match is only a deterministic classification—it does not by itself establish that the term is a validated trend, a demand signal, or commercially meaningful.

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

The live Google Trends endpoint requires `GOOGLE_TRENDS_BIGQUERY_PROJECT_ID` and Application Default Credentials with BigQuery access. `GOOGLE_TRENDS_REFRESH_DATE` is optional for the live endpoint: a valid recent value is preferred, while missing, future, or stale values start a bounded 14-day search from the current UTC date. The temporary protected preflight continues to require an explicit refresh date.

## Model and data limitations

The 300-row dataset is deterministic synthetic demo data created for this reconstruction. It is not the unavailable original dataset, so its metrics and predictions are not expected to reproduce the historical approximate values in the brief. The training script reports random-split and chronological-split MAE, R², and MAPE, then fits the deployable model on all rows.

`inventory_units` remains a feature for frontend compatibility. In real data this can introduce demand censoring or leakage because observed sales may be constrained by available stock. A production model should distinguish latent demand, observed sales, stock availability, stockouts, and lead time.

Random forests also do not extrapolate reliably beyond training ranges. Production work should add range validation, out-of-distribution warnings, and calibrated confidence indicators.

The current trend score is descriptive ranking, not future forecasting. A true trend model should use lagged mentions and growth, rolling averages and volatility, source breadth, category momentum, seasonality, and a time index to predict next-period growth or future interest.
