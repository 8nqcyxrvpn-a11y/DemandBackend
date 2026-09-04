"""Render-compatible FastAPI entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.collection_service import load_collection
from app.config import COLLECTION_PATH, DATASET_PATH, MODEL_PATH, cors_origins
from app.demand_service import FEATURE_NAMES, predict_demand
from app.model_loader import ArtifactError, load_model
from app.schemas import DemandInput
from app.trend_service import build_trend_signals

logger = logging.getLogger("fashion_intelligence")


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        load_model(MODEL_PATH)
        load_collection(COLLECTION_PATH)
        logger.info("Startup artifact validation passed")
    except ArtifactError:
        logger.exception("Startup artifact validation failed")
    yield


app = FastAPI(title="AI Fashion Intelligence Backend", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "success", "message": "AI Fashion Intelligence Backend is running"}


@app.get("/health")
def health() -> dict[str, object]:
    model_loaded = collection_loaded = False
    try:
        load_model(MODEL_PATH)
        model_loaded = True
    except ArtifactError:
        pass
    try:
        load_collection(COLLECTION_PATH)
        collection_loaded = True
    except ArtifactError:
        pass
    return {
        "status": "healthy" if model_loaded and collection_loaded else "degraded",
        "model_loaded": model_loaded,
        "collection_loaded": collection_loaded,
    }


@app.get("/collection")
def collection() -> dict:
    try:
        return load_collection(COLLECTION_PATH)
    except ArtifactError as exc:
        logger.exception("Collection request failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/predict-demand")
def demand(payload: DemandInput) -> dict:
    try:
        return predict_demand(payload, load_model(MODEL_PATH))
    except ArtifactError as exc:
        logger.exception("Demand request failed")
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Demand inference failed")
        raise HTTPException(status_code=500, detail="Demand prediction failed.") from exc


@app.get("/trend-signals")
def trend_signals() -> dict:
    try:
        signals = build_trend_signals(DATASET_PATH)
    except Exception as exc:
        logger.exception("Trend signal calculation failed")
        raise HTTPException(status_code=503, detail="Synthetic trend data is unavailable.") from exc
    return {"status": "success", "data_source": "synthetic_demo", "is_live_data": False, "signals": signals}


@app.get("/model-info")
def model_info() -> dict:
    return {
        "model_type": "RandomForestRegressor",
        "feature_names": FEATURE_NAMES,
        "target_name": "sales_units",
        "training_data": "synthetic_demo",
        "prototype_warning": "Not validated for real-world commercial forecasting.",
    }

