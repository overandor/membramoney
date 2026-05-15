import httpx
from app.core.config import get_settings

settings = get_settings()
BASE = "https://api.printify.com/v1"
HEADERS = {
    "Authorization": f"Bearer {settings.printify_api_key}",
    "Content-Type": "application/json",
}

async def list_shops():
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/shops.json", headers=HEADERS)
        return r.json()

async def list_blueprints():
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{BASE}/catalog/blueprints.json", headers=HEADERS)
        return r.json()

async def create_product(shop_id: str, payload: dict):
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/shops/{shop_id}/products.json", json=payload, headers=HEADERS)
        return r.json()

async def create_order(shop_id: str, payload: dict):
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{BASE}/shops/{shop_id}/orders.json", json=payload, headers=HEADERS)
        return r.json()

async def get_shipping_rates(blueprint_id: str, print_provider_id: str):
    async with httpx.AsyncClient() as c:
        r = await c.get(
            f"{BASE}/catalog/blueprints/{blueprint_id}/print_providers/{print_provider_id}/shipping/express.json",
            headers=HEADERS,
        )
        return r.json()
