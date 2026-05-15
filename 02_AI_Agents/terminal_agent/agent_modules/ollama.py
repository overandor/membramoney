"""Ollama AI integration agent."""

import logging
import threading
from typing import Dict, List

import requests


class OllamaAgent:
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "phi3:mini"):
        self.base_url = base_url
        self.model = model
        self.conversation_history: Dict[str, List[Dict]] = {}
        self.lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        self.enabled = True

    def check_connection(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except Exception:
            return False

    def get_models(self) -> List[str]:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                data = response.json()
                return [model["name"] for model in data.get("models", [])]
            return []
        except Exception:
            return []

    def chat(self, session_id: str, message: str, system_prompt: str = None) -> str:
        if not self.enabled:
            return "AI is currently disabled due to connection issues."
        with self.lock:
            if session_id not in self.conversation_history:
                self.conversation_history[session_id] = []
            self.conversation_history[session_id].append(
                {"role": "user", "content": message}
            )
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.extend(self.conversation_history[session_id])
            try:
                response = requests.post(
                    f"{self.base_url}/api/chat",
                    json={"model": self.model, "messages": messages, "stream": False},
                    timeout=30,
                )
                if response.status_code == 200:
                    result = response.json()
                    assistant_message = result.get("message", {}).get("content", "")
                    if assistant_message:
                        self.conversation_history[session_id].append(
                            {"role": "assistant", "content": assistant_message}
                        )
                        if len(self.conversation_history[session_id]) > 50:
                            self.conversation_history[session_id] = self.conversation_history[session_id][-50:]
                        return assistant_message
                    return "AI returned empty response. The model may not be ready."
                error_msg = f"Error: Ollama returned status {response.status_code}"
                self.logger.error(error_msg)
                if response.status_code >= 500:
                    self.enabled = False
                    return f"{error_msg}. AI disabled temporarily. Please restart Ollama."
                return error_msg
            except requests.Timeout:
                self.logger.warning("Ollama request timed out")
                return "Error: Request timed out. Ollama may be busy."
            except Exception as e:
                self.logger.error(f"Ollama error: {e}")
                return f"Error: {e}"

    def clear_history(self, session_id: str):
        with self.lock:
            if session_id in self.conversation_history:
                del self.conversation_history[session_id]

    def set_model(self, model: str):
        self.model = model

    def enable(self):
        self.enabled = True
        self.logger.info("AI re-enabled")
