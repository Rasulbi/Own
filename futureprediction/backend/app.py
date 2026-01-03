# app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from datetime import datetime
import random
import csv
import os
import statistics

# ---------- Config ----------
HOST = "0.0.0.0"
PORT = 5000
MOCK_CSV = "mock_prices.csv"  # optional CSV file you can provide (see generator below)

# ---------- FastAPI setup ----------
app = FastAPI(title="FutureCrop - Price Prediction API")

# Allow CORS for local frontend (dev). In production restrict origins.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # for dev; change to your frontend origin in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Request/Response Schemas ----------
class PredictRequest(BaseModel):
    state: str = Field(..., example="Andhra Pradesh")
    district: Optional[str] = Field(None, example="Visakhapatnam")
    market: Optional[str] = Field(None, example="Main Market")
    crop: str = Field(..., example="Tomato")
    month: str = Field(..., example="2025-12")  # YYYY-MM

class PredictResponse(BaseModel):
    state: str
    district: Optional[str]
    market: Optional[str]
    crop: str
    month: str
    unit: str
    currentPrice: float
    predictedPrice: float
    method: str

# ---------- Mock data loader ----------
# Expected CSV format (optional): state,district,market,crop,date,price,unit
def load_mock_data(csv_path=MOCK_CSV):
    data = []
    if not os.path.exists(csv_path):
        return data
    with open(csv_path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                row_price = float(row.get("price") or 0)
            except:
                row_price = 0.0
            data.append({
                "state": row.get("state", "").strip(),
                "district": row.get("district", "").strip(),
                "market": row.get("market", "").strip(),
                "crop": row.get("crop", "").strip(),
                "date": row.get("date", "").strip(),
                "price": row_price,
                "unit": row.get("unit", "kg").strip() or "kg"
            })
    return data

MOCK_DATA = load_mock_data()

# helpers
def month_to_date(ym: str):
    # ym like "2025-12"
    try:
        return datetime.strptime(ym + "-01", "%Y-%m-%d")
    except:
        raise ValueError("month must be YYYY-MM")

def find_recent_price(state, district, crop, market):
    """
    Try to find a recent price from mock dataset; fallback to None.
    """
    if not MOCK_DATA:
        return None
    # filter by crop and state (prefer exact district/market matches)
    def matches(row):
        if row["crop"].lower() != crop.lower():
            return False
        if state and row["state"].lower() != state.lower():
            return False
        # allow district/market to be optional
        if district and row["district"]:
            if row["district"].lower() != district.lower():
                return False
        if market and row["market"]:
            if row["market"].lower() != (market.lower()):
                return False
        return True

    candidates = [r for r in MOCK_DATA if matches(r)]
    if not candidates:
        # relax filters: match only crop (global)
        candidates = [r for r in MOCK_DATA if r["crop"].lower() == crop.lower()]
    if not candidates:
        return None
    # pick latest by date if date present, else median
    with_dates = []
    for r in candidates:
        try:
            d = datetime.strptime(r["date"], "%Y-%m-%d")
            with_dates.append((d, r))
        except:
            continue
    if with_dates:
        with_dates.sort(key=lambda x: x[0], reverse=True)
        return with_dates[0][1]  # most recent record
    # else return median-priced record
    prices = [r["price"] for r in candidates if r["price"] > 0]
    if prices:
        med = statistics.median(prices)
        r = candidates[0].copy()
        r["price"] = med
        return r
    return None

# ---------- Simple placeholder prediction function ----------
def simple_predict(current_price: float, months_ahead: int = 1, crop: str = ""):
    """
    Placeholder rule-based predictor. Replace with ML model later.
    Strategy:
      - add small seasonal/random delta based on crop categories
    """
    # base volatility by crop (rough categories)
    low_vol = {"rice", "wheat", "maize", "paddy"}
    med_vol = {"onion", "tomato", "potato", "capsicum", "brinjal"}
    high_vol = {"tomato", "onion"}  # more variable

    c = crop.lower()
    vol = 0.05  # default 5% per month
    if any(x in c for x in low_vol):
        vol = 0.02
    elif any(x in c for x in med_vol):
        vol = 0.06
    elif any(x in c for x in high_vol):
        vol = 0.12

    # random walk over months_ahead
    price = current_price
    for _ in range(months_ahead):
        # monthly percentage change drawn from normal with std=vol
        change_pct = random.gauss(0, vol)
        price = max(0.01, price * (1 + change_pct))
    # also add slight upward bias for demonstration
    price = round(price * (1 + 0.01 * months_ahead), 2)
    return price

# ---------- Endpoint ----------
@app.post("/predict", response_model=PredictResponse)
async def predict(req: PredictRequest):
    # Validate month
    try:
        target_date = month_to_date(req.month)
    except ValueError:
        raise HTTPException(status_code=400, detail="month must be in YYYY-MM format")

    # months ahead relative to "now"
    now = datetime.now()
    months_ahead = (target_date.year - now.year) * 12 + (target_date.month - now.month)
    if months_ahead < 0:
        months_ahead = 0  # if user sends past month, predict current

    # Try to get current price from mock data
    record = find_recent_price(req.state, req.district or "", req.crop, req.market or "")

    if record and record.get("price", 0) > 0:
        current_price = float(record["price"])
        unit = record.get("unit", "kg") or "kg"
        method = "mock-data"
    else:
        # fallback: synthetic base price by crop -> simple deterministic mapping
        base_map = {
            "tomato": 18.0, "onion": 22.0, "potato": 15.0,
            "rice": 30.0, "wheat": 25.0, "maize": 20.0,
            "banana": 30.0, "mango": 50.0
        }
        current_price = float(base_map.get(req.crop.lower(), random.uniform(10, 40)))
        unit = "kg"
        method = "synthetic"

    predicted_price = simple_predict(current_price, months_ahead=months_ahead, crop=req.crop)

    # Response
    return PredictResponse(
        state=req.state,
        district=req.district,
        market=req.market,
        crop=req.crop,
        month=req.month,
        unit=unit,
        currentPrice=round(current_price, 2),
        predictedPrice=round(predicted_price, 2),
        method=method
    )

# ---------- Health / info ----------
@app.get("/")
def root():
    return {"app": "FutureCrop Prediction API", "version": "0.1", "endpoints": ["/predict (POST)"]}

# ---------- If run directly ----------
if _name_ == "_main_":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=5000, reload=True)
# generate_mock_csv.py
import csv
from random import choice, uniform, randint
from datetime import datetime, timedelta

states = ["Andhra Pradesh","Karnataka","Telangana","Maharashtra","Tamil Nadu"]
districts = ["Visakhapatnam","Hyderabad","Bengaluru","Pune","Chennai"]
markets = ["Main Market","Wholesale Yard","Central Mandai","Local Market"]
crops = ["Tomato","Onion","Potato","Rice","Wheat"]

with open("mock_prices.csv", "w", newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(["state","district","market","crop","date","price","unit"])
    for _ in range(1000):
        state = choice(states)
        district = choice(districts)
        market = choice(markets)
        crop = choice(crops)
        days_ago = randint(0, 365)
        dt = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        price = round(uniform(8.0, 60.0), 2)
        unit = "kg"
        writer.writerow([state, district, market, crop, dt, price, unit])
print("mock_prices.csv generated")