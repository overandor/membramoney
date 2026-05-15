import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "Membra API"
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./membra.db")
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-me")
    insurance_provider_url: str = os.getenv("INSURANCE_PROVIDER_URL", "")
    payment_provider_url: str = os.getenv("PAYMENT_PROVIDER_URL", "")
    qr_secret: str = os.getenv("QR_SECRET", "dev-qr-secret")
    access_window_minutes: int = 15
    dispute_window_hours: int = 24

    class Config:
        env_file = ".env"

settings = Settings()
