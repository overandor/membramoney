from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import json
import uuid

from app.db.base import get_db
from app.models.chat import Chat
from app.models.user import User
from app.schemas.chat import ChatCreate, ChatResponse, ChatDetailResponse, PublishRequest
from app.services.normalizer import detect_and_normalize
from app.api.deps import get_current_active_user
from app.core.config import settings

router = APIRouter()


@router.post("/upload", response_model=ChatResponse)
async def upload_chat(
    file: UploadFile = File(...),
    title: str = None,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Validate file size
    content = await file.read()
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit"
        )
    
    # Validate file type
    if not file.filename.endswith('.json'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only JSON files are allowed"
        )
    
    # Parse JSON
    try:
        chat_data = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON format"
        )
    
    # Extract metadata if present (from GPT Bridge)
    chat_title = chat_data.get("title") if isinstance(chat_data, dict) else None
    chat_model = chat_data.get("model") if isinstance(chat_data, dict) else None
    chat_messages = chat_data.get("messages") if isinstance(chat_data, dict) else chat_data
    
    # Normalize chat data
    normalized_messages = detect_and_normalize(chat_data)
    
    if not normalized_messages:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid messages found in chat data"
        )
    
    # Create chat record
    chat = Chat(
        user_id=current_user.id,
        title=title or chat_title or file.filename,
        model=chat_model,
        original_data=chat_data,
        normalized_data=normalized_messages,
        is_public=False,
        message_count=len(normalized_messages)
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)
    
    return chat


@router.get("/", response_model=List[ChatResponse])
def list_chats(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    chats = db.query(Chat).filter(
        Chat.user_id == current_user.id
    ).order_by(Chat.created_at.desc()).offset(skip).limit(limit).all()
    return chats


@router.get("/public", response_model=List[ChatResponse])
def list_public_chats(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    chats = db.query(Chat).filter(
        Chat.is_public == True
    ).order_by(Chat.created_at.desc()).offset(skip).limit(limit).all()
    return chats


@router.get("/{chat_id}", response_model=ChatDetailResponse)
def get_chat(
    chat_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )
    
    # Check ownership or public access
    if chat.user_id != current_user.id and not chat.is_public:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied"
        )
    
    return chat


@router.post("/{chat_id}/publish", response_model=ChatResponse)
def publish_chat(
    chat_id: str,
    publish_request: PublishRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )
    
    # Check ownership
    if chat.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can publish this chat"
        )
    
    chat.is_public = publish_request.is_public
    db.commit()
    db.refresh(chat)
    
    return chat


@router.delete("/{chat_id}")
def delete_chat(
    chat_id: str,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    chat = db.query(Chat).filter(Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat not found"
        )
    
    # Check ownership
    if chat.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner can delete this chat"
        )
    
    db.delete(chat)
    db.commit()
    
    return {"message": "Chat deleted successfully"}
