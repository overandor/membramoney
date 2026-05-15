import json
import websockets
from ..config import settings

class RealtimeBridge:
    def __init__(self, task_id: int, instructions: str):
        self.task_id = task_id
        self.instructions = instructions
        self.transcript_parts: list[str] = []

    async def open(self):
        # Skeleton only: this opens a Realtime session endpoint.
        # You still need to map Twilio media frames to/from the session format you choose.
        self.ws = await websockets.connect(
            "wss://api.openai.com/v1/realtime",
            additional_headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "OpenAI-Beta": "realtime=v1",
            },
        )

        session_update = {
            "type": "session.update",
            "session": {
                "model": settings.openai_realtime_model,
                "instructions": (
                    f"{settings.disclosure_line} "
                    "You are a phone agent. Complete the task if possible. "
                    "Do not claim to be the user. "
                    f"Task instructions: {self.instructions}"
                )
            }
        }
        await self.ws.send(json.dumps(session_update))

    async def close(self):
        if getattr(self, "ws", None):
            await self.ws.close()
