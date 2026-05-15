"""
CleanStat Infrastructure - Security Module
Production-hardened JWT token management with refresh tokens
"""
import jwt
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from passlib.context import CryptContext
from app.config import settings
from app.db.redis_client import redis_client

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def create_access_token(wallet: str, org_id: str, role: str) -> str:
    """Create JWT access token"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    jti = secrets.token_urlsafe(16)
    payload = {
        "sub": wallet,
        "org": org_id,
        "role": role,
        "exp": expire,
        "jti": jti,
        "type": "access"
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def create_refresh_token(wallet: str, jti: str) -> str:
    """Create JWT refresh token and store in Redis"""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": wallet,
        "exp": expire,
        "jti": jti,
        "type": "refresh"
    }
    token = jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    # Store refresh token in Redis with expiration
    redis_client.setex(f"refresh:{jti}", settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, token)
    return token

def verify_token(token: str) -> Optional[dict]:
    """Verify JWT token and check revocation status"""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        # Check if refresh token is revoked (for refresh tokens)
        if payload.get("type") == "refresh":
            stored = redis_client.get(f"refresh:{payload['jti']}")
            if not stored or stored != token:
                return None
        return payload
    except jwt.PyJWTError:
        return None

def revoke_refresh_token(jti: str):
    """Revoke refresh token by removing from Redis"""
    redis_client.delete(f"refresh:{jti}")

# Nonce handling (MetaMask auth)
def generate_nonce(wallet: str) -> str:
    """Generate and store nonce for wallet signature"""
    nonce = f"Sign this message to login to CleanStat: {secrets.token_urlsafe(16)}"
    redis_client.setex(f"nonce:{wallet}", 300, nonce)
    return nonce

def verify_nonce(wallet: str, signature: str) -> Tuple[bool, Optional[str]]:
    """Verify wallet signature against stored nonce"""
    nonce = redis_client.get(f"nonce:{wallet}")
    if not nonce:
        return False, "Nonce expired or not found"
    # Verify signature using web3.py
    from web3.auto import w3
    from eth_account.messages import encode_defunct
    message = encode_defunct(text=nonce)
    try:
        recovered = w3.eth.account.recover_message(message, signature=signature)
        if recovered.lower() == wallet.lower():
            redis_client.delete(f"nonce:{wallet}")  # One-time use
            return True, None
        return False, "Invalid signature"
    except Exception:
        return False, "Signature verification failed"
