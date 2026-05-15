from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from app.auth_service import (
    NonceRequest,
    NonceResponse,
    VerifyRequest,
    AuthResponse,
    RoleUpdateRequest,
    issue_nonce,
    verify_signature,
    logout as auth_logout,
    get_current_user,
    require_role,
    USERS,
    LOGIN_HTML,
    extract_token_from_request,
    get_user_from_request_optional,
    revoke_token_if_present,
    VALID_ROLES,
    normalize_wallet
)
from app.core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/nonce", response_model=NonceResponse)
def create_nonce(req: NonceRequest):
    """
    Issue a nonce for wallet signature
    """
    return issue_nonce(req)


@router.post("/verify", response_model=AuthResponse)
def verify_wallet_signature(req: VerifyRequest):
    """
    Verify wallet signature and issue JWT token
    """
    return verify_signature(req)


@router.post("/logout")
def logout(request: Request):
    """
    Logout and revoke token
    """
    token = extract_token_from_request(request)
    revoke_token_if_present(token)

    response = JSONResponse({"ok": True})
    response.delete_cookie("access_token")
    return response


@router.get("/me")
def get_current_user_info(user: dict = Depends(get_current_user)):
    """
    Get current authenticated user info
    """
    return user


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    """
    Login page with MetaMask integration
    """
    user = get_user_from_request_optional(request)
    if user:
        return RedirectResponse(url="/app")
    return HTMLResponse(LOGIN_HTML)


# ============================================================
# ADMIN ENDPOINTS
# ============================================================

@router.get("/admin/users")
def list_users(user: dict = Depends(require_role("admin"))):
    """
    List all users (admin only)
    """
    logger.info("Admin listing users", admin_wallet=user["wallet_address"])
    return {"data": list(USERS.values())}


@router.post("/admin/users/{wallet_address}/role")
def set_user_role(
    wallet_address: str,
    body: RoleUpdateRequest,
    user: dict = Depends(require_role("admin"))
):
    """
    Set user role (admin only)
    """
    wallet = normalize_wallet(wallet_address)
    if wallet not in USERS:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found")

    if body.role not in VALID_ROLES:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Invalid role")

    USERS[wallet]["role"] = body.role
    logger.info(
        "Admin updated user role",
        admin_wallet=user["wallet_address"],
        target_wallet=wallet,
        new_role=body.role
    )
    return {"ok": True, "user": USERS[wallet]}
