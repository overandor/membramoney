from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    database_url: str = "sqlite:///./membra_ads.db"
    supabase_url: str = ""
    supabase_key: str = ""
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_platform_account_id: str = ""
    printful_api_key: str = ""
    printify_api_key: str = ""
    gelato_api_key: str = ""
    gototags_api_key: str = ""
    secret_key: str = "change-me"
    frontend_url: str = "http://localhost:3000"
    api_url: str = "http://localhost:8000"
    environment: str = "development"
    qr_base_url: str = "https://membra.app/t"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()
