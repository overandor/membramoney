import json
import hashlib
from typing import Optional
from src.db.database import get_connection, now_iso, generate_id
from src.models.schemas import ProofRecordCreate, ProofRecordOut
from src.core.exceptions import MembraError

def _hash_record(record_type: str, record_id: str, raw_data: dict) -> str:
    payload = json.dumps({"type": record_type, "id": record_id, "data": raw_data}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()

def create_proof_record(data: ProofRecordCreate) -> ProofRecordOut:
    raw = data.raw_data or {}
    h = _hash_record(data.record_type, data.record_id, raw)
    conn = get_connection()
    pid = generate_id("prf_")
    conn.execute(
        "INSERT INTO proof_records (proof_id, record_type, record_id, hash, raw_data, signatures, verified, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (pid, data.record_type, data.record_id, h,
         json.dumps(raw) if raw else None,
         json.dumps(data.signatures) if data.signatures else None,
         0, now_iso()),
    )
    conn.commit()
    conn.close()
    return get_proof_record(pid)

def get_proof_record(proof_id: str) -> Optional[ProofRecordOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM proof_records WHERE proof_id = ?", (proof_id,)).fetchone()
    conn.close()
    return _row_to_proof(row) if row else None

def list_proof_records(record_type: Optional[str] = None, record_id: Optional[str] = None, limit: int = 100) -> list[ProofRecordOut]:
    conn = get_connection()
    sql = "SELECT * FROM proof_records WHERE 1=1"
    params = []
    if record_type:
        sql += " AND record_type = ?"
        params.append(record_type)
    if record_id:
        sql += " AND record_id = ?"
        params.append(record_id)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_proof(r) for r in rows]

def verify_proof(proof_id: str) -> ProofRecordOut:
    conn = get_connection()
    conn.execute("UPDATE proof_records SET verified = 1 WHERE proof_id = ?", (proof_id,))
    conn.commit()
    conn.close()
    p = get_proof_record(proof_id)
    if not p:
        raise MembraError("Proof record disappeared")
    return p

def _row_to_proof(row) -> ProofRecordOut:
    return ProofRecordOut(
        proof_id=row["proof_id"],
        record_type=row["record_type"],
        record_id=row["record_id"],
        hash=row["hash"],
        raw_data=json.loads(row["raw_data"]) if row["raw_data"] else None,
        signatures=json.loads(row["signatures"]) if row["signatures"] else None,
        verified=bool(row["verified"]),
        created_at=row["created_at"],
    )
