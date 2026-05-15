"""Terminal session management."""

import secrets
import threading
from datetime import datetime
from typing import Dict, List, Optional, Set


class TerminalSession:
    def __init__(self, session_id: str, owner: str):
        self.session_id = session_id
        self.owner = owner
        self.participants: Set[str] = {owner}
        self.output: List[Dict] = []
        self.lock = threading.Lock()
        self.created = datetime.now().isoformat()

    def add_output(self, content: str, type: str = "output", user: str = None):
        with self.lock:
            self.output.append(
                {"content": content, "type": type, "user": user,
                 "timestamp": datetime.now().isoformat()}
            )
            if len(self.output) > 1000:
                self.output = self.output[-1000:]

    def get_output(self, since: int = 0) -> List[Dict]:
        with self.lock:
            return self.output[since:]

    def add_participant(self, username: str):
        with self.lock:
            self.participants.add(username)

    def remove_participant(self, username: str):
        with self.lock:
            self.participants.discard(username)


class TerminalSessionManager:
    def __init__(self):
        self.sessions: Dict[str, TerminalSession] = {}
        self.lock = threading.Lock()

    def create_session(self, owner: str) -> TerminalSession:
        session_id = secrets.token_hex(16)
        with self.lock:
            session = TerminalSession(session_id, owner)
            self.sessions[session_id] = session
            return session

    def get_session(self, session_id: str) -> Optional[TerminalSession]:
        with self.lock:
            return self.sessions.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        with self.lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                return True
            return False

    def list_sessions(self) -> List[Dict]:
        with self.lock:
            return [
                {
                    "session_id": s.session_id,
                    "owner": s.owner,
                    "participants": list(s.participants),
                    "created": s.created,
                    "output_count": len(s.output),
                }
                for s in self.sessions.values()
            ]
