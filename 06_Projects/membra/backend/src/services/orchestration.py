import json
from typing import Optional
from src.db.database import get_connection, now_iso, generate_id
from src.models.schemas import ObjectiveCreate, ObjectiveOut, TaskCreate, TaskOut
from src.core.exceptions import MembraError

def create_objective(data: ObjectiveCreate) -> ObjectiveOut:
    conn = get_connection()
    oid = generate_id("obj_")
    conn.execute(
        "INSERT INTO objectives (objective_id, owner_id, title, description, status, priority, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (oid, data.owner_id, data.title, data.description or "", "draft", data.priority, now_iso(), now_iso()),
    )
    conn.commit()
    conn.close()
    return get_objective(oid)

def get_objective(objective_id: str) -> Optional[ObjectiveOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM objectives WHERE objective_id = ?", (objective_id,)).fetchone()
    conn.close()
    return _row_to_objective(row) if row else None

def list_objectives(owner_id: Optional[str] = None, status: Optional[str] = None) -> list[ObjectiveOut]:
    conn = get_connection()
    sql = "SELECT * FROM objectives WHERE 1=1"
    params = []
    if owner_id:
        sql += " AND owner_id = ?"
        params.append(owner_id)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_objective(r) for r in rows]

def update_objective_status(objective_id: str, status: str) -> ObjectiveOut:
    conn = get_connection()
    conn.execute("UPDATE objectives SET status = ?, updated_at = ? WHERE objective_id = ?", (status, now_iso(), objective_id))
    conn.commit()
    conn.close()
    o = get_objective(objective_id)
    if not o:
        raise MembraError("Objective disappeared")
    return o

# ─── Tasks ──────────────────────────────────────────────────
def create_task(data: TaskCreate) -> TaskOut:
    conn = get_connection()
    tid = generate_id("tsk_")
    conn.execute(
        """
        INSERT INTO tasks (task_id, objective_id, title, description, assignee_type, assignee_id, status, priority, deadline, proof_requirement, depends_on, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (tid, data.objective_id, data.title, data.description or "", data.assignee_type, data.assignee_id,
         "pending", data.priority,
         data.deadline.isoformat() if data.deadline else None,
         data.proof_requirement, data.depends_on, now_iso(), now_iso()),
    )
    conn.commit()
    conn.close()
    return get_task(tid)

def get_task(task_id: str) -> Optional[TaskOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
    conn.close()
    return _row_to_task(row) if row else None

def list_tasks(objective_id: Optional[str] = None, assignee_id: Optional[str] = None, status: Optional[str] = None) -> list[TaskOut]:
    conn = get_connection()
    sql = "SELECT * FROM tasks WHERE 1=1"
    params = []
    if objective_id:
        sql += " AND objective_id = ?"
        params.append(objective_id)
    if assignee_id:
        sql += " AND assignee_id = ?"
        params.append(assignee_id)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_task(r) for r in rows]

def update_task_status(task_id: str, status: str, assignee_id: Optional[str] = None) -> TaskOut:
    conn = get_connection()
    set_clauses = ["status = ?", "updated_at = ?"]
    params = [status, now_iso()]
    if assignee_id:
        set_clauses.append("assignee_id = ?")
        params.append(assignee_id)
    params.append(task_id)
    conn.execute(f"UPDATE tasks SET {', '.join(set_clauses)} WHERE task_id = ?", params)
    conn.commit()
    conn.close()
    t = get_task(task_id)
    if not t:
        raise MembraError("Task disappeared")
    return t

# ─── Row mappers ──────────────────────────────────────────
def _row_to_objective(row) -> ObjectiveOut:
    return ObjectiveOut(
        objective_id=row["objective_id"],
        owner_id=row["owner_id"],
        title=row["title"],
        description=row["description"] or None,
        status=row["status"],
        priority=row["priority"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )

def _row_to_task(row) -> TaskOut:
    return TaskOut(
        task_id=row["task_id"],
        objective_id=row["objective_id"] or None,
        title=row["title"],
        description=row["description"] or None,
        assignee_type=row["assignee_type"],
        assignee_id=row["assignee_id"] or None,
        status=row["status"],
        priority=row["priority"],
        deadline=row["deadline"],
        proof_requirement=row["proof_requirement"] or None,
        depends_on=row["depends_on"] or None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
