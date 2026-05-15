import httpx
from app.core.config import get_settings

settings = get_settings()
BASE = "https://api.gelato.com"
HEADERS = {
    "X-API-KEY": settings.gelato_api_key,
    "Content-Type": "application/json",
}

async def create_order(payload: dict):
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/v4/orders", json=payload, headers=HEADERS)
        return r.json()

async def get_order(order_id: str):
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/v3/orders/{order_id}", headers=HEADERS)
        return r.json()

async def list_shipment_methods():
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/v1/shipment-methods", headers=HEADERS)
        return r.json()
