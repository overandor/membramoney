from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models import Task
from ..schemas import TaskCreate, StartTaskResponse
from ..services.twilio_client import create_outbound_call

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("")
def create_task(payload: TaskCreate, session: Session = Depends(get_session)):
    task = Task(
        title=payload.title,
        instructions=payload.instructions,
        phone_number=payload.phone_number,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task

@router.get("")
def list_tasks(session: Session = Depends(get_session)):
    return session.exec(select(Task).order_by(Task.id.desc())).all()

@router.get("/{task_id}")
def get_task(task_id: int, session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task

@router.post("/{task_id}/start", response_model=StartTaskResponse)
def start_task(task_id: int, session: Session = Depends(get_session)):
    task = session.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    call_sid = create_outbound_call(task_id=task.id, to_number=task.phone_number)
    task.call_sid = call_sid
    task.status = "calling"
    task.updated_at = datetime.utcnow()
    session.add(task)
    session.commit()

    return StartTaskResponse(task_id=task.id, status=task.status, call_sid=call_sid)
