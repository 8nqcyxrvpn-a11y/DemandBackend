from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import joblib
import math
from pathlib import Path

app = FastAPI()

# Allow Lovable to connect to this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------
# LOAD COLLECTION DATA
# ------------------------------------------

COLLECTION_FILE = Path(__file__).with_name("final_ai_collection.json")

with open(COLLECTION_FILE, "r", encoding="utf-8") as f:
    collection_data = json.load(f)


# ------------------------------------------
# LOAD TRAINED DEMAND MODEL
# ------------------------------------------

MODEL_FILE = Path(__file__).with_name("demand_model.joblib")

demand_model = joblib.load(MODEL_FILE)


# ------------------------------------------
# INPUT FORMAT FOR DEMAND FORECAST
# ------------------------------------------

class DemandInput(BaseModel):
    price_usd: float
    trend_mentions: float
    trend_growth_pct: float
    inventory_units: float


# ------------------------------------------
# BASIC ROUTES
# ------------------------------------------

@app.get("/")
def home():
    return {
        "status": "success",
        "message": "AI Fashion Intelligence Backend is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


# ------------------------------------------
# COLLECTION ENDPOINT
# ------------------------------------------

@app.get("/collection")
def get_collection():
    return collection_data


# ------------------------------------------
# DYNAMIC DEMAND FORECAST ENDPOINT
# ------------------------------------------

@app.post("/predict-demand")
def predict_demand(data: DemandInput):

    model_input = [[
        data.price_usd,
        data.trend_mentions,
        data.trend_growth_pct,
        data.inventory_units
    ]]

    predicted_demand = float(
        demand_model.predict(model_input)[0]
    )

    safety_stock = math.ceil(
        predicted_demand * 0.15
    )

    recommended_inventory = math.ceil(
        predicted_demand + safety_stock
    )

    return {
        "status": "success",
        "model": "RandomForestRegressor",
        "prediction_type": "dynamic",
        "inputs": {
            "price_usd": data.price_usd,
            "trend_mentions": data.trend_mentions,
            "trend_growth_pct": data.trend_growth_pct,
            "inventory_units": data.inventory_units
        },
        "forecast": {
            "predicted_demand_units": round(predicted_demand),
            "safety_stock_units": safety_stock,
            "recommended_inventory_units": recommended_inventory
        },
        "note": "Prototype forecast trained on synthetic demo data."
    }
