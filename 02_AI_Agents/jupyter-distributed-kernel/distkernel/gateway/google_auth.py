"""
Google OAuth2 + Drive integration for teleportable notebook state.
No single-node dependency - all state persists in Google Drive.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

import aiohttp
from aiohttp import web

log = logging.getLogger("distkernel.google")

# Google OAuth2 settings - these would normally come from env vars
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8555/auth/google/callback")

# In-memory token store (production would use Redis/DB)
_google_tokens: Dict[str, Dict[str, Any]] = {}
_drive_files: Dict[str, Dict[str, Any]] = {}  # user_id -> file metadata


@dataclass
class GoogleUser:
    user_id: str
    email: str
    name: str = ""
    picture: str = ""
    access_token: str = ""
    refresh_token: str = ""
    expires_at: float = 0.0
    drive_folder_id: Optional[str] = None


def get_auth_url(state: str = "") -> str:
    """Generate Google OAuth2 authorization URL."""
    scopes = [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive.appdata",
    ]
    scope_str = "%20".join(scopes)
    return (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={GOOGLE_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={scope_str}"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&state={state}"
    )


async def exchange_code(code: str) -> Optional[Dict[str, Any]]:
    """Exchange OAuth2 code for tokens."""
    async with aiohttp.ClientSession() as session:
        payload = {
            "code": code,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "redirect_uri": GOOGLE_REDIRECT_URI,
            "grant_type": "authorization_code",
        }
        async with session.post(
            "https://oauth2.googleapis.com/token",
            data=payload,
        ) as resp:
            if resp.status != 200:
                log.error("Token exchange failed: %s", await resp.text())
                return None
            return await resp.json()


async def refresh_access_token(refresh_token: str) -> Optional[str]:
    """Refresh expired access token."""
    async with aiohttp.ClientSession() as session:
        payload = {
            "refresh_token": refresh_token,
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "grant_type": "refresh_token",
        }
        async with session.post(
            "https://oauth2.googleapis.com/token",
            data=payload,
        ) as resp:
            if resp.status != 200:
                log.error("Token refresh failed: %s", await resp.text())
                return None
            data = await resp.json()
            return data.get("access_token")


async def get_user_info(access_token: str) -> Optional[Dict[str, Any]]:
    """Get user profile from Google."""
    async with aiohttp.ClientSession() as session:
        headers = {"Authorization": f"Bearer {access_token}"}
        async with session.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers=headers,
        ) as resp:
            if resp.status != 200:
                return None
            return await resp.json()


class DriveStorage:
    """Google Drive storage for notebook state."""
    
    NOTEBOOK_FILENAME = "distkernel_notebook.json"
    
    def __init__(self, user: GoogleUser):
        self._user = user
        self._folder_id: Optional[str] = None
    
    async def _ensure_folder(self) -> Optional[str]:
        """Ensure DistKernel folder exists in Drive."""
        if self._folder_id:
            return self._folder_id
        
        # Search for existing folder
        folder = await self._find_file("DistKernel", mime_type="application/vnd.google-apps.folder")
        if folder:
            self._folder_id = folder["id"]
            self._user.drive_folder_id = folder["id"]
            return folder["id"]
        
        # Create new folder
        return await self._create_folder("DistKernel")
    
    async def _get_headers(self) -> Dict[str, str]:
        """Get auth headers, refreshing token if needed."""
        if time.time() > self._user.expires_at:
            new_token = await refresh_access_token(self._user.refresh_token)
            if new_token:
                self._user.access_token = new_token
                self._user.expires_at = time.time() + 3600
        return {"Authorization": f"Bearer {self._user.access_token}"}
    
    async def _find_file(self, name: str, mime_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Find a file in Drive."""
        headers = await self._get_headers()
        q = f"name='{name}' and trashed=false"
        if mime_type:
            q += f" and mimeType='{mime_type}'"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.googleapis.com/drive/v3/files",
                headers=headers,
                params={"q": q, "spaces": "drive,appDataFolder"},
            ) as resp:
                if resp.status != 200:
                    log.error("Drive search failed: %s", await resp.text())
                    return None
                data = await resp.json()
                files = data.get("files", [])
                return files[0] if files else None
    
    async def _create_folder(self, name: str) -> Optional[str]:
        """Create a folder in Drive."""
        headers = await self._get_headers()
        metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://www.googleapis.com/drive/v3/files",
                headers={**headers, "Content-Type": "application/json"},
                json=metadata,
            ) as resp:
                if resp.status not in (200, 201):
                    log.error("Folder creation failed: %s", await resp.text())
                    return None
                data = await resp.json()
                self._folder_id = data["id"]
                self._user.drive_folder_id = data["id"]
                return data["id"]
    
    async def save_notebook(self, session_id: str, cells: List[Dict[str, Any]]) -> bool:
        """Save notebook state to Google Drive."""
        folder_id = await self._ensure_folder()
        if not folder_id:
            return False
        
        headers = await self._get_headers()
        content = json.dumps({
            "session_id": session_id,
            "timestamp": time.time(),
            "cells": cells,
        }, indent=2)
        
        # Check if file exists
        existing = await self._find_file(self.NOTEBOOK_FILENAME)
        
        async with aiohttp.ClientSession() as session:
            if existing:
                # Update existing file
                async with session.patch(
                    f"https://www.googleapis.com/drive/v3/files/{existing['id']}",
                    headers={**headers, "Content-Type": "application/json"},
                    json={"name": self.NOTEBOOK_FILENAME},
                ) as resp:
                    if resp.status not in (200, 204):
                        log.error("File update failed: %s", await resp.text())
                        return False
                
                # Upload new content
                async with session.patch(
                    f"https://www.googleapis.com/upload/drive/v3/files/{existing['id']}?uploadType=media",
                    headers={**headers, "Content-Type": "application/json"},
                    data=content,
                ) as resp:
                    return resp.status in (200, 204)
            else:
                # Create new file
                metadata = {
                    "name": self.NOTEBOOK_FILENAME,
                    "parents": [folder_id],
                    "mimeType": "application/json",
                }
                
                # Multipart upload
                boundary = "----DistKernelBoundary"
                body = (
                    f"--{boundary}\r\n"
                    f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
                    f"{json.dumps(metadata)}\r\n"
                    f"--{boundary}\r\n"
                    f"Content-Type: application/json\r\n\r\n"
                    f"{content}\r\n"
                    f"--{boundary}--"
                ).encode()
                
                async with session.post(
                    "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
                    headers={
                        **headers,
                        "Content-Type": f"multipart/related; boundary={boundary}",
                    },
                    data=body,
                ) as resp:
                    if resp.status not in (200, 201):
                        log.error("File creation failed: %s", await resp.text())
                        return False
                    return True
    
    async def load_notebook(self) -> Optional[Dict[str, Any]]:
        """Load notebook state from Google Drive."""
        existing = await self._find_file(self.NOTEBOOK_FILENAME)
        if not existing:
            return None
        
        headers = await self._get_headers()
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://www.googleapis.com/drive/v3/files/{existing['id']}?alt=media",
                headers=headers,
            ) as resp:
                if resp.status != 200:
                    log.error("File download failed: %s", await resp.text())
                    return None
                content = await resp.text()
                try:
                    return json.loads(content)
                except json.JSONDecodeError:
                    return None


# ─── Helper functions for server integration ─────────────────────────────────

def store_user(user: GoogleUser) -> None:
    """Store user in memory (production: use Redis/DB)."""
    _google_tokens[user.user_id] = {
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
        "access_token": user.access_token,
        "refresh_token": user.refresh_token,
        "expires_at": user.expires_at,
        "drive_folder_id": user.drive_folder_id,
    }


def get_user(user_id: str) -> Optional[GoogleUser]:
    """Get user from memory store."""
    data = _google_tokens.get(user_id)
    if not data:
        return None
    return GoogleUser(
        user_id=user_id,
        email=data["email"],
        name=data.get("name", ""),
        picture=data.get("picture", ""),
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=data["expires_at"],
        drive_folder_id=data.get("drive_folder_id"),
    )


def get_all_google_users() -> List[Dict[str, Any]]:
    """Get list of all connected Google users."""
    now = time.time()
    return [
        {
            "user_id": uid,
            "email": d["email"],
            "name": d.get("name", ""),
            "picture": d.get("picture", ""),
            "online": (now - d.get("last_active", 0)) < 300,
        }
        for uid, d in _google_tokens.items()
    ]


def update_last_active(user_id: str) -> None:
    """Update last active timestamp."""
    if user_id in _google_tokens:
        _google_tokens[user_id]["last_active"] = time.time()
