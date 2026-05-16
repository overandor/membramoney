from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
from typing import Optional


_PLACEHOLDER_VALUES = {
    "change-me-in-production-32-char-key",
    "change-me-pepper-32-char-long!!!",
    "change-me-claim-secret-32chars!!",
}


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "CoinPack Redemption API"
    DEBUG: bool = False
    ENV: str = "development"

    # Solana
    SOLANA_RPC_URL: str = "https://api.devnet.solana.com"
    SOLANA_WS_URL: str = "wss://api.devnet.solana.com"
    PROGRAM_ID: str = "Fg6PaFpoGXkYsidMpWTK6W2BeZ7FEfcYkg476zPFsLnS"
    VAULT_SEED: str = "vault"
    NOTE_SEED: str = "note"
    CLAIM_SEED: str = "claim"

    # BTC Reserve
    BTC_RESERVE_WALLET_XPUB: Optional[str] = None
    BTC_RESERVE_MULTISIG_THRESHOLD: int = 2
    BTC_RESERVE_SIGNERS: int = 3
    BTC_NETWORK: str = "mainnet"  # mainnet or testnet

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://coinpack:coinpack@localhost:5432/coinpack"
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = Field(default="change-me-in-production-32-char-key", min_length=32)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    PIN_MAX_ATTEMPTS: int = 5
    PIN_LOCKOUT_MINUTES: int = 30
    CLAIM_EXPIRATION_HOURS: int = 24
    PIN_PEPPER: str = Field(default="change-me-pepper-32-char-long!!!", min_length=32)
    CLAIM_LINK_SECRET: str = Field(default="change-me-claim-secret-32chars!!", min_length=32)
    ADMIN_API_TOKEN: Optional[str] = Field(default=None, min_length=32)
    ENCRYPTION_KEY: Optional[str] = None

    # Reserve
    MIN_RESERVE_RATIO_BPS: int = 10_000  # 100% = 10000 bps
    MEMPOOL_API_BASE: str = "https://mempool.space/api"

    # Frontend
    FRONTEND_BASE_URL: str = "http://localhost:3000"
    CORS_ORIGINS: str = "http://localhost:3000"  # Comma-separated; never use * in production

    # Delivery providers
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_FROM_NUMBER: Optional[str] = None
    SENDGRID_API_KEY: Optional[str] = None

    # Rate limiting
    RATE_LIMIT_AUTH: int = 5  # per minute
    RATE_LIMIT_API: int = 100  # per minute
    RATE_LIMIT_CLAIM: int = 10  # per minute

    # Monitoring
    SENTRY_DSN: Optional[str] = None
    LOG_LEVEL: str = "INFO"

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def is_production(self) -> bool:
        return self.ENV.lower() in {"prod", "production", "mainnet"}

    def cors_origins_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
        if not origins:
            raise ValueError("CORS_ORIGINS must contain at least one explicit origin")
        if self.is_production and "*" in origins:
            raise ValueError("Wildcard CORS is forbidden in production")
        return origins

    def validate_production_security(self) -> None:
        """Fail fast when production-like deployments still use unsafe defaults."""
        if not self.is_production:
            return

        unsafe = []
        for name in ("SECRET_KEY", "PIN_PEPPER", "CLAIM_LINK_SECRET"):
            value = getattr(self, name)
            if value in _PLACEHOLDER_VALUES or value.startswith("change-me"):
                unsafe.append(name)

        if not self.ADMIN_API_TOKEN or self.ADMIN_API_TOKEN in _PLACEHOLDER_VALUES:
            unsafe.append("ADMIN_API_TOKEN")

        if "coinpack:coinpack@" in self.DATABASE_URL:
            unsafe.append("DATABASE_URL")

        if unsafe:
            raise ValueError(
                "Unsafe production configuration values: " + ", ".join(sorted(set(unsafe)))
            )


settings = Settings()
