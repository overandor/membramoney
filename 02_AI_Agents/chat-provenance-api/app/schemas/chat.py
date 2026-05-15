from pydantic import BaseModel
from typing import Optional, List, Any, Dict
from datetime import datetime


class ChatCreate(BaseModel):
    title: Optional[str] = None


class ChatResponse(BaseModel):
    id: str
    user_id: str
    title: Optional[str]
    model: Optional[str]
    is_public: bool
    message_count: int
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class ChatDetailResponse(ChatResponse):
    original_data: Any
    normalized_data: List[Dict[str, Any]]  # Now [{role, content}, ...]


class PublishRequest(BaseModel):
    is_public: bool
