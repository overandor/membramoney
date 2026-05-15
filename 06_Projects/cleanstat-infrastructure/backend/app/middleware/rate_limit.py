"""
CleanStat Infrastructure - Rate Limiting Middleware
API rate limiting using slowapi
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_API_PER_MINUTE}/minute"]
)
