from typing import Optional
from pydantic import BaseModel

class TaskCreate(BaseModel):
    title: str
    instructions: str
    phone_number: str

class TaskRead(BaseModel):
    id: int
    title: str
    instructions: str
    phone_number: str
    status: str
    call_sid: Optional[str] = None
    transcript: Optional[str] = None
    summary: Optional[str] = None

class StartTaskResponse(BaseModel):
    task_id: int
    status: str
    call_sid: Optional[str]
