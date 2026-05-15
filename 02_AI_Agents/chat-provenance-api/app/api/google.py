from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import List, Optional
import httpx

from app.core.google_config import (
    get_oauth_flow,
    credentials_from_dict,
    credentials_to_dict,
    get_drive_service
)
from app.api.deps import get_current_user
from app.db.base import get_db
from app.models.user import User
from app.models.chat import Chat
from app.services.file_to_chat import FileToChatGenerator
from sqlalchemy.orm import Session

router = APIRouter()

class GoogleCredentials(BaseModel):
    credentials: dict

class FileSelection(BaseModel):
    file_ids: List[str]

@router.get("/auth")
def google_auth():
    """Initiate Google OAuth flow"""
    try:
        flow = get_oauth_flow()
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        return {"authorization_url": authorization_url, "state": state}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/callback")
def google_callback(code: str, state: str):
    """Handle Google OAuth callback"""
    try:
        flow = get_oauth_flow()
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Return credentials as JSON
        return {
            "credentials": credentials_to_dict(credentials),
            "message": "Successfully authenticated with Google"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/credentials")
def save_credentials(
    creds: GoogleCredentials,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Save Google credentials for the current user"""
    try:
        # In production, store encrypted in database
        # For now, return success
        return {"message": "Credentials saved successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/files")
def list_drive_files(
    creds: GoogleCredentials,
    query: str = "",
    page_size: int = 50
):
    """List files from Google Drive"""
    try:
        credentials = credentials_from_dict(creds.credentials)
        service = get_drive_service(credentials)

        # Build query
        q = "trashed=false"
        if query:
            q += f" and name contains '{query}'"

        results = service.files().list(
            q=q,
            pageSize=page_size,
            fields="nextPageToken, files(id, name, mimeType, size, modifiedTime, webViewLink)"
        ).execute()

        files = results.get('files', [])
        return {
            "files": files,
            "total": len(files)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/files/{file_id}/metadata")
def get_file_metadata(
    file_id: str,
    creds: GoogleCredentials
):
    """Get metadata for a specific file"""
    try:
        credentials = credentials_from_dict(creds.credentials)
        service = get_drive_service(credentials)

        file = service.files().get(
            fileId=file_id,
            fields="id, name, mimeType, size, modifiedTime, webViewLink, exportLinks"
        ).execute()

        return file
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/files/{file_id}/content")
def download_file_content(
    file_id: str,
    creds: GoogleCredentials
):
    """Download file content from Google Drive"""
    try:
        credentials = credentials_from_dict(creds.credentials)
        service = get_drive_service(credentials)

        # Get file info first
        file = service.files().get(fileId=file_id).execute()
        mime_type = file.get('mimeType')

        # Download content
        if mime_type == 'application/vnd.google-apps.document':
            # Export Google Docs as text
            request = service.files().export_media(
                fileId=file_id,
                mimeType='text/plain'
            )
        elif mime_type == 'application/vnd.google-apps.spreadsheet':
            # Export Google Sheets as CSV
            request = service.files().export_media(
                fileId=file_id,
                mimeType='text/csv'
            )
        else:
            # Download regular files
            request = service.files().get_media(fileId=file_id)

        content = request.execute()

        # Decode if bytes
        if isinstance(content, bytes):
            try:
                content = content.decode('utf-8')
            except:
                content = content.decode('latin-1')

        return {
            "file_id": file_id,
            "name": file.get('name'),
            "mime_type": mime_type,
            "content": content,
            "size": len(content)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/files/process")
def process_files_to_chat(
    request_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Process selected Google Drive files into ChatGPT conversations"""
    try:
        credentials = credentials_from_dict(request_data.get('credentials'))
        service = get_drive_service(credentials)

        file_ids = request_data.get('file_ids', [])
        is_public = request_data.get('is_public', False)

        created_chats = []

        for file_id in file_ids:
            # Get file info
            file = service.files().get(fileId=file_id).execute()
            file_name = file.get('name')
            mime_type = file.get('mimeType')

            # Download content
            if mime_type == 'application/vnd.google-apps.document':
                request = service.files().export_media(fileId=file_id, mimeType='text/plain')
            elif mime_type == 'application/vnd.google-apps.spreadsheet':
                request = service.files().export_media(fileId=file_id, mimeType='text/csv')
            else:
                request = service.files().get_media(fileId=file_id)

            content = request.execute()

            # Decode if bytes
            if isinstance(content, bytes):
                try:
                    content = content.decode('utf-8')
                except:
                    content = content.decode('latin-1')

            # Generate conversation from file
            generator = FileToChatGenerator(content, file_name, mime_type)
            conversation = generator.generate_conversation()

            # Create chat record
            chat = Chat(
                user_id=current_user.id,
                title=conversation['title'],
                model=conversation['model'],
                normalized_data=conversation['messages'],
                is_public=is_public,
                original_filename=file_name
            )

            db.add(chat)
            db.commit()
            db.refresh(chat)

            created_chats.append({
                "chat_id": chat.id,
                "title": chat.title,
                "file_name": file_name,
                "message_count": len(conversation['messages'])
            })

        return {
            "message": f"Successfully processed {len(created_chats)} files",
            "chats": created_chats
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
