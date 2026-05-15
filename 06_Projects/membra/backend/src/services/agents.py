import json
from typing import Optional
from src.db.database import get_connection, now_iso, generate_id
from src.models.schemas import AgentCreate, AgentOut
from src.core.exceptions import MembraError

def create_agent(data: AgentCreate) -> AgentOut:
    conn = get_connection()
    aid = generate_id("agt_")
    conn.execute(
        """
        INSERT INTO agents (agent_id, name, role, description, tools, permissions, blocked_actions, output_schema, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (aid, data.name, data.role, data.description or "",
         json.dumps(data.tools) if data.tools else None,
         json.dumps(data.permissions) if data.permissions else None,
         json.dumps(data.blocked_actions) if data.blocked_actions else None,
         json.dumps(data.output_schema) if data.output_schema else None,
         "active", now_iso()),
    )
    conn.commit()
    conn.close()
    return get_agent(aid)

def get_agent(agent_id: str) -> Optional[AgentOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM agents WHERE agent_id = ?", (agent_id,)).fetchone()
    conn.close()
    return _row_to_agent(row) if row else None

def list_agents(role: Optional[str] = None, status: Optional[str] = None) -> list[AgentOut]:
    conn = get_connection()
    sql = "SELECT * FROM agents WHERE 1=1"
    params = []
    if role:
        sql += " AND role = ?"
        params.append(role)
    if status:
        sql += " AND status = ?"
        params.append(status)
    sql += " ORDER BY created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [_row_to_agent(r) for r in rows]

def update_agent_status(agent_id: str, status: str) -> AgentOut:
    conn = get_connection()
    conn.execute("UPDATE agents SET status = ? WHERE agent_id = ?", (status, agent_id))
    conn.commit()
    conn.close()
    a = get_agent(agent_id)
    if not a:
        raise MembraError("Agent disappeared")
    return a

def _row_to_agent(row) -> AgentOut:
    return AgentOut(
        agent_id=row["agent_id"],
        name=row["name"],
        role=row["role"],
        description=row["description"] or None,
        tools=json.loads(row["tools"]) if row["tools"] else None,
        permissions=json.loads(row["permissions"]) if row["permissions"] else None,
        blocked_actions=json.loads(row["blocked_actions"]) if row["blocked_actions"] else None,
        output_schema=json.loads(row["output_schema"]) if row["output_schema"] else None,
        status=row["status"],
        created_at=row["created_at"],
    )
