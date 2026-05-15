from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

class Settings(BaseModel):
    app_base_url: str = os.getenv("APP_BASE_URL", "http://localhost:8000")
    public_ws_base: str = os.getenv("PUBLIC_WS_BASE", "ws://localhost:8000")

    twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    twilio_from_number: str = os.getenv("TWILIO_FROM_NUMBER", "")

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_realtime_model: str = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-1.5")

    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    sqlite_path: str = os.getenv("SQLITE_PATH", "./morning_agent.db")
    disclosure_line: str = os.getenv(
        "DISCLOSURE_LINE",
        "Hello, this is Joseph's AI assistant calling on his behalf."
    )

settings = Settings()
