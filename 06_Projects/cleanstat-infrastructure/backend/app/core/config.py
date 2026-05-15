"""
CleanStat Infrastructure - Configuration
Production-ready settings management
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List, Optional
from enum import Enum


class Environment(str, Enum):
    """Application environment"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class Settings(BaseSettings):
    """
    Application settings
    All configuration loaded from environment variables
    """
    
    # ============================================================
    # APPLICATION
    # ============================================================
    app_name: str = "cleanstat"
    app_version: str = "1.0.0"
    environment: Environment = Environment.PRODUCTION
    debug: bool = False
    
    # ============================================================
    # DATABASE
    # ============================================================
    database_url: str
    database_pool_size: int = 20
    database_max_overflow: int = 40
    database_echo: bool = False
    
    # ============================================================
    # REDIS
    # ============================================================
    redis_url: str
    redis_cache_ttl: int = 3600
    redis_max_connections: int = 50
    
    # ============================================================
    # CELERY
    # ============================================================
    celery_broker_url: str
    celery_result_backend: str
    celery_task_time_limit: int = 3600
    celery_task_soft_time_limit: int = 3000
    
    # ============================================================
    # SECURITY
    # ============================================================
    secret_key: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_exp_hours: int = 8
    access_token_expire_minutes: int = 480
    
    # ============================================================
    # AUTHENTICATION
    # ============================================================
    seeded_admin_wallet: str
    nonce_expiration_seconds: int = 300
    max_login_attempts: int = 5
    login_lockout_minutes: int = 30
    
    # ============================================================
    # IPFS / PINATA
    # ============================================================
    pinata_api_key: Optional[str] = None
    pinata_api_secret: Optional[str] = None
    pinata_gateway: str = "https://gateway.pinata.cloud"
    ipfs_timeout: int = 30
    
    # ============================================================
    # BLOCKCHAIN
    # ============================================================
    ethereum_rpc_url: Optional[str] = None
    ethereum_chain_id: int = 1
    contract_address: Optional[str] = None
    private_key: Optional[str] = None
    gas_price_gwei: int = 30
    gas_limit: int = 100000
    
    # ============================================================
    # NYC 311 INTEGRATION
    # ============================================================
    nyc_311_api_url: str = "https://api.nyc.gov/311"
    nyc_311_api_key: Optional[str] = None
    nyc_311_timeout: int = 30
    nyc_311_rate_limit: int = 100
    
    # ============================================================
    # RATE LIMITING
    # ============================================================
    rate_limit_per_minute: int = 100
    rate_limit_per_hour: int = 1000
    rate_limit_per_day: int = 10000
    
    # ============================================================
    # FILE STORAGE
    # ============================================================
    upload_dir: str = "/var/lib/cleanstat/uploads"
    max_upload_size_mb: int = 50
    allowed_image_types: str = "image/jpeg,image/png,image/webp"
    image_quality: int = 85
    image_max_dimension: int = 4096
    
    # ============================================================
    # AI DETECTION
    # ============================================================
    ai_detection_timeout: int = 60
    ai_detection_confidence_threshold: float = 0.75
    ai_detection_model_version: str = "v2.0"
    
    # ============================================================
    # LOGGING
    # ============================================================
    log_level: str = "INFO"
    log_format: str = "json"
    sentry_dsn: Optional[str] = None
    log_retention_days: int = 90
    
    # ============================================================
    # MONITORING
    # ============================================================
    metrics_enabled: bool = True
    metrics_port: int = 9090
    health_check_interval: int = 30
    
    # ============================================================
    # CORS
    # ============================================================
    cors_origins: List[str] = ["https://cleanstat.io", "https://app.cleanstat.io"]
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_allow_headers: List[str] = ["*"]
    
    # ============================================================
    # NOTIFICATIONS
    # ============================================================
    slack_webhook_url: Optional[str] = None
    email_smtp_host: Optional[str] = None
    email_smtp_port: int = 587
    email_smtp_user: Optional[str] = None
    email_smtp_password: Optional[str] = None
    email_from: str = "noreply@cleanstat.io"
    
    # ============================================================
    # BACKUP
    # ============================================================
    backup_enabled: bool = True
    backup_schedule: str = "0 2 * * *"
    backup_retention_days: int = 30
    backup_s3_bucket: Optional[str] = None
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.environment == Environment.PRODUCTION
    
    @property
    def is_development(self) -> bool:
        """Check if running in development"""
        return self.environment == Environment.DEVELOPMENT


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    """
    return Settings()
