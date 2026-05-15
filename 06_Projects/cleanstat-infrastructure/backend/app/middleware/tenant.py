"""
CleanStat Infrastructure - Tenant Isolation Middleware
Multi-tenant authentication and authorization
"""
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import verify_token
from app.models.user import User

async def get_current_user(request: Request, db: Session = Depends(get_db)):
    """Get current authenticated user from JWT token"""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(401, "Not authenticated")
    payload = verify_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(401, "Invalid token")
    user = db.query(User).filter(User.wallet_address == payload["sub"]).first()
    if not user:
        raise HTTPException(401, "User not found")
    return user

def require_role(*allowed_roles):
    """Role-based access control decorator"""
    async def role_checker(current_user: User = Depends(get_current_user)):
        if current_user.role.value not in allowed_roles:
            raise HTTPException(403, "Insufficient permissions")
        return current_user
    return role_checker

def tenant_filter(query, user: User):
    """Filter queries by organization ID for tenant isolation"""
    return query.filter_by(organization_id=user.organization_id)
