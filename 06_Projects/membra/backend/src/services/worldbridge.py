import json
from typing import Optional
from src.db.database import get_connection, now_iso, generate_id
from src.models.schemas import WorldAssetCreate, WorldAssetOut
from src.core.exceptions import MembraError

def create_world_asset(data: WorldAssetCreate) -> WorldAssetOut:
    conn = get_connection()
    wid = generate_id("wrd_")
    conn.execute(
        """
        INSERT INTO world_assets (world_asset_id, owner_id, asset_type, title, description, address, latitude, longitude, capabilities, availability_schedule, media_urls, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (wid, data.owner_id, data.asset_type, data.title, data.description or "", data.address or "",
         data.latitude, data.longitude,
         json.dumps(data.capabilities) if data.capabilities else None,
         json.dumps(data.availability_schedule) if data.availability_schedule else None,
         json.dumps(data.media_urls) if data.media_urls else None,
         "active", now_iso()),
    )
    conn.commit()
    conn.close()
    return get_world_asset(wid)

def get_world_asset(world_asset_id: str) -> Optional[WorldAssetOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM world_assets WHERE world_asset_id = ?", (world_asset_id,)).fetchone()
    conn.close()
    return _row_to_world_asset(row) if row else None

def list_world_assets(asset_type: Optional[str] = None, owner_id: Optional[str] = None, status: Optional[str] = None) -> list[WorldAssetOut]:
    conn = get_connection()
    sql = "SELECT * FROM world_assets WHERE 1=1"
    params = []
    if asset_type:
        sql += " AND asset_type = ?"
        params.append(asset_type)
    if owner_id:
        sql += " AND owner_id = ?"
        params.append(owner_id)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_world_asset(r) for r in rows]

def update_world_asset_status(world_asset_id: str, status: str) -> WorldAssetOut:
    conn = get_connection()
    conn.execute("UPDATE world_assets SET status = ? WHERE world_asset_id = ?", (status, world_asset_id))
    conn.commit()
    conn.close()
    a = get_world_asset(world_asset_id)
    if not a:
        raise MembraError("World asset disappeared")
    return a

def _row_to_world_asset(row) -> WorldAssetOut:
    return WorldAssetOut(
        world_asset_id=row["world_asset_id"],
        owner_id=row["owner_id"],
        asset_type=row["asset_type"],
        title=row["title"],
        description=row["description"] or None,
        address=row["address"] or None,
        latitude=row["latitude"],
        longitude=row["longitude"],
        capabilities=json.loads(row["capabilities"]) if row["capabilities"] else None,
        availability_schedule=json.loads(row["availability_schedule"]) if row["availability_schedule"] else None,
        media_urls=json.loads(row["media_urls"]) if row["media_urls"] else None,
        status=row["status"],
        created_at=row["created_at"],
    )
