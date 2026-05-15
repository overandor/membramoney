"""User management with authentication and sessions."""

import hashlib
import json
import secrets
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class UserManager:
    def __init__(self, users_file: str = "users.json"):
        self.users_file = Path(users_file)
        self.users: Dict[str, Dict] = {}
        self.sessions: Dict[str, Dict] = {}
        self.lock = threading.Lock()
        self.load_users()

    def load_users(self):
        if self.users_file.exists():
            with open(self.users_file, "r") as f:
                self.users = json.load(f)
        else:
            self.users = {
                "admin": {
                    "password": self.hash_password("admin123"),
                    "role": "admin",
                    "created": datetime.now().isoformat(),
                }
            }
            self.save_users()
            print("Created default admin user (username: admin, password: admin123)")

    def save_users(self):
        with open(self.users_file, "w") as f:
            json.dump(self.users, f, indent=2)

    def hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def verify_password(self, username: str, password: str) -> bool:
        if username not in self.users:
            return False
        return self.users[username]["password"] == self.hash_password(password)

    def create_user(self, username: str, password: str, role: str = "user") -> bool:
        with self.lock:
            if username in self.users:
                return False
            self.users[username] = {
                "password": self.hash_password(password),
                "role": role,
                "created": datetime.now().isoformat(),
            }
            self.save_users()
            return True

    def delete_user(self, username: str) -> bool:
        with self.lock:
            if username == "admin":
                return False
            if username in self.users:
                del self.users[username]
                self.save_users()
                return True
            return False

    def list_users(self) -> List[Dict]:
        with self.lock:
            return [
                {"username": u, "role": user["role"], "created": user["created"]}
                for u, user in self.users.items()
            ]

    def create_session(self, username: str) -> str:
        token = secrets.token_hex(32)
        with self.lock:
            self.sessions[token] = {
                "username": username,
                "created": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
            }
        return token

    def verify_session(self, token: str) -> Optional[str]:
        with self.lock:
            if token in self.sessions:
                self.sessions[token]["last_activity"] = datetime.now().isoformat()
                return self.sessions[token]["username"]
            return None

    def revoke_session(self, token: str) -> bool:
        with self.lock:
            if token in self.sessions:
                del self.sessions[token]
                return True
            return False

    def get_active_sessions(self) -> List[Dict]:
        with self.lock:
            return [
                {"username": s["username"], "created": s["created"],
                 "last_activity": s["last_activity"]}
                for s in self.sessions.values()
            ]
