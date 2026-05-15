"""
CleanStat Infrastructure - Production Configuration
Production-hardened settings with validation
"""
import os
import secrets
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 40

    # Redis
    REDIS_URL: str

    # Security
    JWT_SECRET: str = secrets.token_urlsafe(32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    COOKIE_DOMAIN: Optional[str] = None
    COOKIE_SECURE: bool = True

    # IPFS (Pinata)
    PINATA_JWT: str
    PINATA_GATEWAY: str = "https://gateway.pinata.cloud"

    # Blockchain
    WEB3_PROVIDER_URI: Optional[str] = None
    VCU_CONTRACT_ADDRESS: Optional[str] = None

    # Rate Limiting
    RATE_LIMIT_AUTH_PER_MINUTE: int = 5
    RATE_LIMIT_API_PER_MINUTE: int = 100

    # Monitoring
    SENTRY_DSN: Optional[str] = None
    PROMETHEUS_ENABLED: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

# Validate critical settings at startup
if settings.ENVIRONMENT == "production":
    assert settings.DATABASE_URL, "DATABASE_URL required in production"
    assert settings.REDIS_URL, "REDIS_URL required in production"
    assert settings.PINATA_JWT, "PINATA_JWT required in production"
    assert settings.COOKIE_SECURE, "COOKIE_SECURE must be True in production"
