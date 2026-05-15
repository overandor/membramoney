"""
CleanStat Infrastructure - Redis Client
Production Redis client with health checks
"""
import redis
from app.config import settings

redis_client = redis.Redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=5,
    socket_timeout=5,
    health_check_interval=30
)

def get_redis():
    return redis_client
