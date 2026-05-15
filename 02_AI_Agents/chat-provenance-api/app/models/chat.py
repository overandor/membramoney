from sqlalchemy import Column, String, DateTime, Boolean, Text, JSON, Integer
from sqlalchemy.sql import func
from app.db.base import Base
import uuid


class Chat(Base):
    __tablename__ = "chats"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=True)
    model = Column(String, nullable=True)
    original_data = Column(JSON, nullable=False)
    normalized_data = Column(JSON, nullable=False)  # Now stores [{role, content}, ...]
    original_filename = Column(String, nullable=True)  # Source file name for Google Drive imports
    is_public = Column(Boolean, default=False)
    message_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
