from typing import Optional
from src.db.database import get_connection, now_iso, generate_id
from src.models.schemas import JobCreate, JobOut
from src.core.exceptions import MembraError

def create_job(data: JobCreate) -> JobOut:
    conn = get_connection()
    jid = generate_id("job_")
    conn.execute(
        """
        INSERT INTO jobs (job_id, task_id, job_type, title, description, reward_cents, currency, status, assignee_id, proof_required, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (jid, data.task_id, data.job_type, data.title, data.description or "", data.reward_cents, data.currency,
         "open", None, int(data.proof_required), now_iso(), now_iso()),
    )
    conn.commit()
    conn.close()
    return get_job(jid)

def get_job(job_id: str) -> Optional[JobOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    conn.close()
    return _row_to_job(row) if row else None

def list_jobs(job_type: Optional[str] = None, status: Optional[str] = None, assignee_id: Optional[str] = None) -> list[JobOut]:
    conn = get_connection()
    sql = "SELECT * FROM jobs WHERE 1=1"
    params = []
    if job_type:
        sql += " AND job_type = ?"
        params.append(job_type)
    if status:
        sql += " AND status = ?"
        params.append(status)
    if assignee_id:
        sql += " AND assignee_id = ?"
        params.append(assignee_id)
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_job(r) for r in rows]

def assign_job(job_id: str, assignee_id: str) -> JobOut:
    conn = get_connection()
    conn.execute("UPDATE jobs SET assignee_id = ?, status = ?, updated_at = ? WHERE job_id = ?",
                 (assignee_id, "assigned", now_iso(), job_id))
    conn.commit()
    conn.close()
    j = get_job(job_id)
    if not j:
        raise MembraError("Job disappeared")
    return j

def complete_job(job_id: str) -> JobOut:
    conn = get_connection()
    conn.execute("UPDATE jobs SET status = ?, updated_at = ? WHERE job_id = ?",
                 ("completed", now_iso(), job_id))
    conn.commit()
    conn.close()
    j = get_job(job_id)
    if not j:
        raise MembraError("Job disappeared")
    return j

def _row_to_job(row) -> JobOut:
    return JobOut(
        job_id=row["job_id"],
        task_id=row["task_id"] or None,
        job_type=row["job_type"],
        title=row["title"],
        description=row["description"] or None,
        reward_cents=row["reward_cents"],
        currency=row["currency"],
        status=row["status"],
        assignee_id=row["assignee_id"] or None,
        proof_required=bool(row["proof_required"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
