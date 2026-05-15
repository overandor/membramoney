"""MEMBRA CompanyOS — Production-grade configuration."""
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field, PostgresDsn, RedisDsn


class Settings(BaseSettings):
    # App
    APP_NAME: str = "MEMBRA CompanyOS"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Database
    DATABASE_URL: PostgresDsn = Field(default="postgresql://membra:membra@localhost:5432/membra_companyos")
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: RedisDsn = Field(default="redis://localhost:6379/0")
    REDIS_PASSWORD: Optional[str] = None

    # Security
    SECRET_KEY: str = Field(min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Ethereum / Wallet Auth
    ETHEREUM_RPC_URL: Optional[str] = None
    CHAIN_ID: int = 1

    # LLM
    GROQ_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    DEFAULT_LLM_PROVIDER: str = "groq"
    DEFAULT_LLM_MODEL: str = "llama-3.3-70b-versatile"

    # Settlement
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    SOLANA_RPC_URL: Optional[str] = None
    SOLANA_PRIVATE_KEY: Optional[str] = None

    # IPFS / Proof
    IPFS_GATEWAY: str = "https://gateway.pinata.cloud"
    PINATA_API_KEY: Optional[str] = None
    PINATA_SECRET_KEY: Optional[str] = None

    # Monitoring
    SENTRY_DSN: Optional[str] = None
    PROMETHEUS_PORT: int = 9090

    # CompanyOS
    DEFAULT_COMPANY_NAME: str = "MEMBRA Autonomous Unit"
    DEFAULT_CURRENCY: str = "USD"
    PROOFBOOK_HASH_ALGORITHM: str = "sha3_256"
    GOVERNANCE_ADMIN_WALLET: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
