"""
CleanStat Infrastructure - Authentication Router
Production-hardened authentication with refresh tokens
"""
from fastapi import APIRouter, HTTPException, Response, Request, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from app.db.session import get_db
from app.models.user import User
from app.models.session import Session as DBSession
from app.models.audit_log import AuditLog
from app.core.security import (
    generate_nonce, verify_nonce, create_access_token,
    create_refresh_token, verify_token, revoke_refresh_token
)
from app.middleware.rate_limit import limiter
from app.config import settings
import uuid

router = APIRouter()

class LoginRequest(BaseModel):
    wallet_address: str
    signature: str

class RefreshRequest(BaseModel):
    refresh_token: str

@router.get("/nonce/{wallet_address}")
@limiter.limit(f"{settings.RATE_LIMIT_AUTH_PER_MINUTE}/minute")
async def get_nonce(wallet_address: str, request: Request):
    """Request nonce for wallet signature"""
    nonce = generate_nonce(wallet_address)
    return {"nonce": nonce}

@router.post("/login")
@limiter.limit(f"{settings.RATE_LIMIT_AUTH_PER_MINUTE}/minute")
async def login(
    data: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db)
):
    """Login with wallet signature"""
    # Verify signature
    valid, error = verify_nonce(data.wallet_address, data.signature)
    if not valid:
        audit_log = AuditLog(
            event_type="auth.failure",
            wallet_address=data.wallet_address,
            ip_address=request.client.host,
            details={"reason": error}
        )
        db.add(audit_log)
        db.commit()
        raise HTTPException(401, error)

    # Get user from DB
    user = db.query(User).filter(User.wallet_address == data.wallet_address).first()
    if not user or not user.is_active:
        audit_log = AuditLog(
            event_type="auth.failure",
            wallet_address=data.wallet_address,
            ip_address=request.client.host,
            details={"reason": "User not authorized"}
        )
        db.add(audit_log)
        db.commit()
        raise HTTPException(403, "User not authorized")

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    # Create tokens
    access_token = create_access_token(user.wallet_address, user.organization_id, user.role.value)
    jti = str(uuid.uuid4())
    refresh_token = create_refresh_token(user.wallet_address, jti)

    # Store session in DB
    db_session = DBSession(
        jti=jti,
        wallet_address=user.wallet_address,
        refresh_token=refresh_token,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )
    db.add(db_session)
    db.commit()

    # Audit log
    audit_log = AuditLog(
        event_type="auth.success",
        wallet_address=user.wallet_address,
        organization_id=user.organization_id,
        ip_address=request.client.host
    )
    db.add(audit_log)
    db.commit()

    # Set HTTP-only cookies
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/auth/refresh"  # Only sent to refresh endpoint
    )

    return {"status": "success", "role": user.role.value}

@router.post("/refresh")
async def refresh_token(request: Request, response: Response, db: Session = Depends(get_db)):
    """Refresh access token using refresh token"""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(401, "No refresh token")

    payload = verify_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(401, "Invalid refresh token")

    # Check DB session
    session = db.query(DBSession).filter(
        DBSession.jti == payload["jti"],
        DBSession.revoked == False,
        DBSession.expires_at > datetime.now(timezone.utc)
    ).first()
    if not session:
        raise HTTPException(401, "Session expired or revoked")

    user = db.query(User).filter(User.wallet_address == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(403, "User inactive")

    # Issue new access token
    new_access = create_access_token(user.wallet_address, user.organization_id, user.role.value)
    response.set_cookie(
        key="access_token",
        value=new_access,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
    return {"status": "success"}

@router.post("/logout")
async def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """Logout and revoke tokens"""
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        payload = verify_token(refresh_token)
        if payload:
            revoke_refresh_token(payload["jti"])
            # Mark session revoked in DB
            db.query(DBSession).filter(DBSession.jti == payload["jti"]).update({"revoked": True})
            db.commit()
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"status": "logged out"}
