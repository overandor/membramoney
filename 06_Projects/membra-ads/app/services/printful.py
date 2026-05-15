import httpx
from app.core.config import get_settings

settings = get_settings()

BASE = "https://api.printful.com/v2"
HEADERS = {"Authorization": f"Bearer {settings.printful_api_key}"}

async def list_catalog_categories():
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/catalog-categories", headers=HEADERS)
        return r.json()

async def get_catalog_product(product_id: str):
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/catalog-products/{product_id}", headers=HEADERS)
        return r.json()

async def create_order(store_id: str, payload: dict):
    async with httpx.AsyncClient() as c:
        r = await c.post(
            f"{BASE}/stores/{store_id}/orders",
            json=payload,
            headers={**HEADERS, "Content-Type": "application/json"}
        )
        return r.json()

async def get_order(store_id: str, order_id: str):
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/stores/{store_id}/orders/{order_id}", headers=HEADERS)
        return r.json()

async def estimate_order(payload: dict):
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/order-estimation-tasks", json=payload, headers={**HEADERS, "Content-Type": "application/json"})
        return r.json()
