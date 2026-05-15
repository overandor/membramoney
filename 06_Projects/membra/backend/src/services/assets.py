import math
from typing import Optional
from src.db.database import get_connection, now_iso, generate_id
from src.models.enums import AssetCategory
from src.models.schemas import AssetCreate, AssetOut, NearbyQuery
from src.core.exceptions import MembraError

def create_asset(data: AssetCreate) -> AssetOut:
    conn = get_connection()
    asset_id = generate_id("ast_")
    conn.execute(
        """
        INSERT INTO assets (asset_id, host_id, title, description, category, address, latitude, longitude,
            price_cents, deposit_cents, rules, hours_open, max_guests, insurable, verified, active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            asset_id, data.host_id, data.title, data.description, data.category.value,
            data.address, data.latitude, data.longitude, data.price_cents, data.deposit_cents,
            data.rules, data.hours_open, data.max_guests, int(data.insurable), 0, 1, now_iso(),
        ),
    )
    conn.commit()
    conn.close()
    return get_asset(asset_id)

def get_asset(asset_id: str) -> Optional[AssetOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_asset(row)

def list_assets(category: Optional[AssetCategory] = None, active_only: bool = True) -> list[AssetOut]:
    conn = get_connection()
    sql = "SELECT * FROM assets WHERE 1=1"
    params: list = []
    if category:
        sql += " AND category = ?"
        params.append(category.value)
    if active_only:
        sql += " AND active = 1"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_asset(r) for r in rows]

def nearby_assets(query: NearbyQuery) -> list[AssetOut]:
    # Haversine filter in Python for simplicity; production uses PostGIS
    conn = get_connection()
    rows = conn.execute("SELECT * FROM assets WHERE active = 1").fetchall()
    conn.close()
    results = []
    for row in rows:
        d = _haversine(query.lat, query.lng, row["latitude"], row["longitude"])
        if d <= query.radius_miles:
            results.append(_row_to_asset(row))
    return results

def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3959  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def _row_to_asset(row: dict) -> AssetOut:
    return AssetOut(
        asset_id=row["asset_id"],
        host_id=row["host_id"],
        title=row["title"],
        description=row["description"],
        category=AssetCategory(row["category"]),
        address=row["address"],
        latitude=row["latitude"],
        longitude=row["longitude"],
        price_cents=row["price_cents"],
        deposit_cents=row["deposit_cents"],
        rules=row["rules"],
        hours_open=row["hours_open"],
        max_guests=row["max_guests"],
        insurable=bool(row["insurable"]),
        verified=bool(row["verified"]),
        active=bool(row["active"]),
        created_at=row["created_at"],
    )
