from fastapi import FastAPI
from pydantic import BaseModel
import math

app = FastAPI()


class DemandInput(BaseModel):
    price_usd: float
    trend_mentions: float
    trend_growth_pct: float
    inventory_units: float


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
