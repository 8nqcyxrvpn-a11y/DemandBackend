from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import json
from pathlib import Path

app = FastAPI()

# Allow Lovable to read this backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the collection JSON stored beside this server file
COLLECTION_FILE = Path(__file__).with_name("final_ai_collection.json")

with open(COLLECTION_FILE, "r", encoding="utf-8") as f:
    collection_data = json.load(f)


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


@app.get("/collection")
def get_collection():
    return collection_data
