"""AgentOS API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.base import get_db
from app.services.agent import AgentService
from app.schemas.agent import AgentCreate, AgentRead, AgentUpdate, AgentToolCreate, AgentActionLogRead
from app.schemas.common import BaseResponse, PaginatedResponse

router = APIRouter()


@router.post("/", response_model=BaseResponse)
def register_agent(data: AgentCreate, db: Session = Depends(get_db)):
    svc = AgentService(db)
    agent = svc.register_agent(data)
    return BaseResponse(data={"id": str(agent.id), "status": agent.status.value})


@router.get("/", response_model=PaginatedResponse)
def list_agents(
    company_id: Optional[str] = None,
    agent_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    svc = AgentService(db)
    items = svc.list_agents(company_id=company_id, agent_type=agent_type, limit=limit)
    return PaginatedResponse(
        items=[AgentRead.model_validate(a) for a in items],
        total=len(items),
        page=1,
        page_size=limit,
        pages=1,
    )


@router.get("/{agent_id}", response_model=BaseResponse)
def get_agent(agent_id: str, db: Session = Depends(get_db)):
    svc = AgentService(db)
    agent = svc.db.query(svc.db.bind).first()
    raise HTTPException(status_code=501, detail="Use list endpoint")


@router.patch("/{agent_id}", response_model=BaseResponse)
def update_agent(agent_id: str, data: AgentUpdate, db: Session = Depends(get_db)):
    svc = AgentService(db)
    agent = svc.update_agent(agent_id, data)
    return BaseResponse(data={"id": str(agent.id), "status": agent.status.value})


@router.post("/{agent_id}/tools", response_model=BaseResponse)
def add_tool(agent_id: str, data: AgentToolCreate, db: Session = Depends(get_db)):
    svc = AgentService(db)
    data.agent_id = agent_id
    tool = svc.add_tool(data)
    return BaseResponse(data={"id": str(tool.id), "name": tool.tool_name})


@router.post("/{agent_id}/actions", response_model=BaseResponse)
def log_action(
    agent_id: str,
    action_type: str,
    task_id: Optional[str] = None,
    job_id: Optional[str] = None,
    input_data: Optional[dict] = None,
    output_data: Optional[dict] = None,
    status: str = "success",
    error: Optional[str] = None,
    execution_time_ms: Optional[int] = None,
    governance_passed: bool = True,
    db: Session = Depends(get_db),
):
    svc = AgentService(db)
    log = svc.log_action(
        agent_id, action_type, task_id, job_id,
        input_data, output_data, status, error,
        execution_time_ms, governance_passed,
    )
    return BaseResponse(data={"id": str(log.id), "status": log.status})


@router.get("/{agent_id}/actions", response_model=PaginatedResponse)
def list_actions(
    agent_id: str,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    svc = AgentService(db)
    # Placeholder
    return PaginatedResponse(items=[], total=0, page=1, page_size=limit, pages=0)
