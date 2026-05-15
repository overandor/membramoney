import json
from typing import Optional
from src.db.database import get_connection, now_iso, generate_id
from src.models.schemas import PolicyCreate, PolicyOut, ApprovalCreate, ApprovalOut, AuditEventOut
from src.core.exceptions import MembraError

def create_policy(data: PolicyCreate) -> PolicyOut:
    conn = get_connection()
    pid = generate_id("pol_")
    conn.execute(
        "INSERT INTO policies (policy_id, name, description, rules, version, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (pid, data.name, data.description or "", json.dumps(data.rules), 1, "active", now_iso(), now_iso()),
    )
    conn.commit()
    conn.close()
    return get_policy(pid)

def get_policy(policy_id: str) -> Optional[PolicyOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM policies WHERE policy_id = ?", (policy_id,)).fetchone()
    conn.close()
    return _row_to_policy(row) if row else None

def list_policies(status: Optional[str] = None) -> list[PolicyOut]:
    conn = get_connection()
    sql = "SELECT * FROM policies WHERE 1=1"
    params = []
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_policy(r) for r in rows]

# ─── Approvals ──────────────────────────────────────────────
def create_approval(data: ApprovalCreate) -> ApprovalOut:
    conn = get_connection()
    aid = generate_id("apr_")
    conn.execute(
        "INSERT INTO approvals (approval_id, request_type, request_id, requester_id, approver_id, status, risk_score, reason, created_at, resolved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (aid, data.request_type, data.request_id, data.requester_id, None, "pending", data.risk_score, data.reason or "", now_iso(), None),
    )
    conn.commit()
    conn.close()
    return get_approval(aid)

def get_approval(approval_id: str) -> Optional[ApprovalOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM approvals WHERE approval_id = ?", (approval_id,)).fetchone()
    conn.close()
    return _row_to_approval(row) if row else None

def list_approvals(request_id: Optional[str] = None, status: Optional[str] = None) -> list[ApprovalOut]:
    conn = get_connection()
    sql = "SELECT * FROM approvals WHERE 1=1"
    params = []
    if request_id:
        sql += " AND request_id = ?"
        params.append(request_id)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_approval(r) for r in rows]

def resolve_approval(approval_id: str, approver_id: str, status: str, reason: str = "") -> ApprovalOut:
    if status not in ("approved", "rejected"):
        raise MembraError("Status must be approved or rejected")
    conn = get_connection()
    conn.execute(
        "UPDATE approvals SET approver_id = ?, status = ?, reason = ?, resolved_at = ? WHERE approval_id = ?",
        (approver_id, status, reason, now_iso(), approval_id),
    )
    conn.commit()
    conn.close()
    a = get_approval(approval_id)
    if not a:
        raise MembraError("Approval disappeared")
    return a

# ─── Audit Events ───────────────────────────────────────────
def log_audit_event(event_type: str, actor_id: str, target_type: str, target_id: str, details: Optional[dict] = None, ip_address: Optional[str] = None, user_agent: Optional[str] = None) -> AuditEventOut:
    conn = get_connection()
    eid = generate_id("aud_")
    conn.execute(
        "INSERT INTO audit_events (event_id, event_type, actor_id, target_type, target_id, details, ip_address, user_agent, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (eid, event_type, actor_id, target_type, target_id,
         json.dumps(details) if details else None, ip_address, user_agent, now_iso()),
    )
    conn.commit()
    conn.close()
    return get_audit_event(eid)

def get_audit_event(event_id: str) -> Optional[AuditEventOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM audit_events WHERE event_id = ?", (event_id,)).fetchone()
    conn.close()
    return _row_to_audit(row) if row else None

def list_audit_events(target_type: Optional[str] = None, target_id: Optional[str] = None, limit: int = 100) -> list[AuditEventOut]:
    conn = get_connection()
    sql = "SELECT * FROM audit_events WHERE 1=1"
    params = []
    if target_type:
        sql += " AND target_type = ?"
        params.append(target_type)
    if target_id:
        sql += " AND target_id = ?"
        params.append(target_id)
    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_audit(r) for r in rows]

# ─── Row mappers ──────────────────────────────────────────
def _row_to_policy(row) -> PolicyOut:
    return PolicyOut(
        policy_id=row["policy_id"],
        name=row["name"],
        description=row["description"] or None,
        rules=json.loads(row["rules"]),
        version=row["version"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )

def _row_to_approval(row) -> ApprovalOut:
    return ApprovalOut(
        approval_id=row["approval_id"],
        request_type=row["request_type"],
        request_id=row["request_id"],
        requester_id=row["requester_id"],
        approver_id=row["approver_id"] or None,
        status=row["status"],
        risk_score=row["risk_score"],
        reason=row["reason"] or None,
        created_at=row["created_at"],
        resolved_at=row["resolved_at"] or None,
    )

def _row_to_audit(row) -> AuditEventOut:
    return AuditEventOut(
        event_id=row["event_id"],
        event_type=row["event_type"],
        actor_id=row["actor_id"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        details=json.loads(row["details"]) if row["details"] else None,
        ip_address=row["ip_address"] or None,
        user_agent=row["user_agent"] or None,
        created_at=row["created_at"],
    )
