"""
CleanStat Infrastructure - Rate Limiting
API rate limiting using slowapi
"""
from slowapi import Limiter
from slowapi.util import get_remote_address
from app.core.config import get_settings

settings = get_settings()

# Create rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.rate_limit_per_minute}/minute"],
    storage_uri=settings.redis_url,
    enabled=True
)


def get_rate_limit_for_user(user_id: str) -> str:
    """
    Get rate limit for specific user based on role
    
    Args:
        user_id: User identifier
    
    Returns:
        Rate limit string
    """
    # In production, this would check user role from database
    # For now, return default limit
    return f"{settings.rate_limit_per_hour}/hour"
