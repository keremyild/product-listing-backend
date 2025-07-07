import json, time, os
from fastapi import FastAPI, Query, HTTPException
from dotenv import load_dotenv
import httpx  # asenkron http istemcisi

load_dotenv()
API_KEY = os.getenv("GOLD_API_KEY")

app = FastAPI()

with open("products.json", encoding="utf-8") as f:
    RAW = json.load(f)

CACHE = {"gold": (0.0, 0.0)}

async def gold_price_per_gram() -> float:
    ts, price = CACHE["gold"]
    if time.time() - ts < 3600:
        return price

    url = "https://www.goldapi.io/api/XAU/USD"
    headers = {"x-access-token": API_KEY, "Content-Type": "application/json"}
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(url, headers=headers)
            r.raise_for_status()
            data = r.json()
            usd_per_gram = data.get("price_gram_24k")
            if usd_per_gram is None:
                raise HTTPException(502, "Altın fiyatı verisi eksik")
            CACHE["gold"] = (time.time(), usd_per_gram)
            return usd_per_gram
    except Exception:
        # Fallback fiyat
        return 60.0

def enrich(p: dict, gold: float):
    p = p.copy()
    p["price"] = round((p["popularityScore"] + 1) * p["weight"] * gold, 2)
    p["popularityFive"] = round(p["popularityScore"] * 5, 1)
    return p

@app.get("/products")
async def list_products(min_price: float | None = Query(None),
                        max_price: float | None = Query(None),
                        min_popularity: float | None = Query(None)):
    gold = await gold_price_per_gram()
    items = [enrich(p, gold) for p in RAW]

    if min_price is not None:
        items = [p for p in items if p["price"] >= min_price]
    if max_price is not None:
        items = [p for p in items if p["price"] <= max_price]
    if min_popularity is not None:
        items = [p for p in items if p["popularityScore"] >= min_popularity]

    return items

@app.get("/products/{idx}")
async def one_product(idx: int):
    if idx < 0 or idx >= len(RAW):
        raise HTTPException(404, "Ürün bulunamadı")
    gold = await gold_price_per_gram()
    return enrich(RAW[idx], gold)
