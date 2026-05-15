import json
from typing import Optional
from src.db.database import get_connection, now_iso, generate_id
from src.models.schemas import DepartmentCreate, DepartmentOut, SOPCreate, SOPOut, OperatingUnitCreate, OperatingUnitOut
from src.core.exceptions import MembraError

def create_department(data: DepartmentCreate) -> DepartmentOut:
    conn = get_connection()
    did = generate_id("dept_")
    conn.execute(
        "INSERT INTO departments (department_id, name, description, parent_id, kpi_targets, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (did, data.name, data.description or "", data.parent_id,
         json.dumps(data.kpi_targets) if data.kpi_targets else None,
         "active", now_iso()),
    )
    conn.commit()
    conn.close()
    return get_department(did)

def get_department(department_id: str) -> Optional[DepartmentOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM departments WHERE department_id = ?", (department_id,)).fetchone()
    conn.close()
    return _row_to_department(row) if row else None

def list_departments() -> list[DepartmentOut]:
    conn = get_connection()
    rows = conn.execute("SELECT * FROM departments ORDER BY created_at DESC").fetchall()
    conn.close()
    return [_row_to_department(r) for r in rows]

# ─── SOPs ───────────────────────────────────────────────────
def create_sop(data: SOPCreate) -> SOPOut:
    conn = get_connection()
    sid = generate_id("sop_")
    conn.execute(
        "INSERT INTO sops (sop_id, department_id, title, steps, trigger_events, status, version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (sid, data.department_id, data.title, json.dumps(data.steps),
         json.dumps(data.trigger_events) if data.trigger_events else None,
         "active", 1, now_iso(), now_iso()),
    )
    conn.commit()
    conn.close()
    return get_sop(sid)

def get_sop(sop_id: str) -> Optional[SOPOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM sops WHERE sop_id = ?", (sop_id,)).fetchone()
    conn.close()
    return _row_to_sop(row) if row else None

def list_sops(department_id: Optional[str] = None) -> list[SOPOut]:
    conn = get_connection()
    sql = "SELECT * FROM sops WHERE 1=1"
    params = []
    if department_id:
        sql += " AND department_id = ?"
        params.append(department_id)
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_sop(r) for r in rows]

# ─── Operating Units ──────────────────────────────────────
def create_operating_unit(data: OperatingUnitCreate) -> OperatingUnitOut:
    conn = get_connection()
    uid = generate_id("unit_")
    conn.execute(
        "INSERT INTO operating_units (unit_id, name, department_id, unit_type, territory, kpi_snapshot, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (uid, data.name, data.department_id, data.unit_type, data.territory or "",
         json.dumps(data.kpi_snapshot) if data.kpi_snapshot else None,
         "active", now_iso()),
    )
    conn.commit()
    conn.close()
    return get_operating_unit(uid)

def get_operating_unit(unit_id: str) -> Optional[OperatingUnitOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM operating_units WHERE unit_id = ?", (unit_id,)).fetchone()
    conn.close()
    return _row_to_unit(row) if row else None

def list_operating_units(department_id: Optional[str] = None) -> list[OperatingUnitOut]:
    conn = get_connection()
    sql = "SELECT * FROM operating_units WHERE 1=1"
    params = []
    if department_id:
        sql += " AND department_id = ?"
        params.append(department_id)
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_unit(r) for r in rows]

# ─── Row mappers ──────────────────────────────────────────
def _row_to_department(row) -> DepartmentOut:
    return DepartmentOut(
        department_id=row["department_id"],
        name=row["name"],
        description=row["description"] or None,
        parent_id=row["parent_id"] or None,
        kpi_targets=json.loads(row["kpi_targets"]) if row["kpi_targets"] else None,
        status=row["status"],
        created_at=row["created_at"],
    )

def _row_to_sop(row) -> SOPOut:
    return SOPOut(
        sop_id=row["sop_id"],
        department_id=row["department_id"],
        title=row["title"],
        steps=json.loads(row["steps"]),
        trigger_events=json.loads(row["trigger_events"]) if row["trigger_events"] else None,
        status=row["status"],
        version=row["version"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )

def _row_to_unit(row) -> OperatingUnitOut:
    return OperatingUnitOut(
        unit_id=row["unit_id"],
        name=row["name"],
        department_id=row["department_id"],
        unit_type=row["unit_type"],
        territory=row["territory"] or None,
        kpi_snapshot=json.loads(row["kpi_snapshot"]) if row["kpi_snapshot"] else None,
        status=row["status"],
        created_at=row["created_at"],
    )
