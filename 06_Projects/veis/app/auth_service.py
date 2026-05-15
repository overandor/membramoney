import os
import time
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional, Any

import jwt
from eth_account import Account
from eth_account.messages import encode_defunct
from fastapi import HTTPException, Header, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel
import gradio as gr

# ============================================================
# CONFIG
# ============================================================

JWT_SECRET = os.environ.get("JWT_SECRET", "change-me-in-production")
JWT_ALG = "HS256"
JWT_EXP_HOURS = int(os.environ.get("JWT_EXP_HOURS", "12"))
APP_TITLE = "VEIS CleanStat Auth Demo"

# ============================================================
# IN-MEMORY STORES
# Replace with DB in production
# ============================================================

NONCES: Dict[str, Dict[str, Any]] = {}
USERS: Dict[str, Dict[str, Any]] = {}
SESSIONS: Dict[str, Dict[str, Any]] = {}

# Seed one admin wallet for demo
# Replace with your real wallet if needed
SEEDED_ADMIN = os.environ.get(
    "SEEDED_ADMIN_WALLET",
    "0x1111111111111111111111111111111111111111"
).lower()

USERS[SEEDED_ADMIN] = {
    "wallet_address": SEEDED_ADMIN,
    "role": "admin",
    "organization_id": "demo-city",
    "status": "active",
    "created_at": datetime.utcnow().isoformat(),
    "last_login_at": None,
}

# ============================================================
# HELPERS
# ============================================================

VALID_ROLES = {"admin", "city_operator", "reviewer", "contractor", "viewer"}

def now_utc() -> datetime:
    return datetime.utcnow()

def normalize_wallet(address: str) -> str:
    if not isinstance(address, str):
        raise HTTPException(status_code=400, detail="Wallet address must be a string")
    if not address.startswith("0x") or len(address) != 42:
        raise HTTPException(status_code=400, detail="Invalid wallet address format")
    return address.lower()

def build_sign_message(wallet: str, nonce: str) -> str:
    return (
        f"{APP_TITLE}\n"
        f"Wallet: {wallet}\n"
        f"Nonce: {nonce}\n"
        "Purpose: Authenticate into VEIS CleanStat.\n"
        "This request will not trigger a blockchain transaction."
    )

def create_jwt(user: dict) -> str:
    issued = now_utc()
    expires = issued + timedelta(hours=JWT_EXP_HOURS)
    jti = secrets.token_hex(16)

    payload = {
        "sub": user["wallet_address"],
        "role": user["role"],
        "org": user.get("organization_id"),
        "iat": int(issued.timestamp()),
        "exp": int(expires.timestamp()),
        "jti": jti,
    }

    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)
    SESSIONS[jti] = {
        "wallet_address": user["wallet_address"],
        "created_at": issued.isoformat(),
        "expires_at": expires.isoformat(),
        "revoked": False,
    }
    return token

def decode_jwt(token: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        jti = payload.get("jti")
        if not jti or jti not in SESSIONS:
            raise HTTPException(status_code=401, detail="Session not found")
        if SESSIONS[jti]["revoked"]:
            raise HTTPException(status_code=401, detail="Session revoked")
        return payload
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")

    token = authorization.replace("Bearer ", "", 1)
    payload = decode_jwt(token)

    wallet = payload["sub"].lower()
    user = USERS.get(wallet)
    if not user or user.get("status") != "active":
        raise HTTPException(status_code=401, detail="User not active or not found")

    return user

def require_role(*roles):
    def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return user
    return checker

def extract_token_from_request(request: Request) -> Optional[str]:
    auth = request.headers.get("authorization")
    if auth and auth.startswith("Bearer "):
        return auth.replace("Bearer ", "", 1)

    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        return cookie_token

    return None

def get_user_from_request_optional(request: Request) -> Optional[dict]:
    token = extract_token_from_request(request)
    if not token:
        return None
    try:
        payload = decode_jwt(token)
        wallet = payload["sub"].lower()
        user = USERS.get(wallet)
        if user and user.get("status") == "active":
            return user
    except Exception:
        return None
    return None

def revoke_token_if_present(token: Optional[str]) -> None:
    if not token:
        return
    try:
        payload = decode_jwt(token)
        jti = payload.get("jti")
        if jti in SESSIONS:
            SESSIONS[jti]["revoked"] = True
    except Exception:
        pass

# ============================================================
# Pydantic models
# ============================================================

class NonceRequest(BaseModel):
    wallet_address: str

class NonceResponse(BaseModel):
    wallet_address: str
    nonce: str
    message: str
    expires_in_seconds: int

class VerifyRequest(BaseModel):
    wallet_address: str
    signature: str

class AuthResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict

class RoleUpdateRequest(BaseModel):
    role: str

# ============================================================
# LOGIN PAGE
# ============================================================

LOGIN_HTML = """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <title>VEIS CleanStat Login</title>
  <style>
    body {
      font-family: Arial, sans-serif;
      background: #0f172a;
      color: #e2e8f0;
      margin: 0;
      padding: 40px;
    }
    .card {
      max-width: 700px;
      margin: 0 auto;
      background: #111827;
      border: 1px solid #334155;
      border-radius: 16px;
      padding: 24px;
      box-shadow: 0 8px 30px rgba(0,0,0,0.35);
    }
    button {
      background: #2563eb;
      color: white;
      border: none;
      border-radius: 10px;
      padding: 12px 16px;
      font-size: 16px;
      cursor: pointer;
      margin-right: 8px;
    }
    button:hover {
      background: #1d4ed8;
    }
    pre {
      background: #020617;
      padding: 12px;
      border-radius: 10px;
      overflow-x: auto;
      white-space: pre-wrap;
      word-wrap: break-word;
    }
    .muted { color: #94a3b8; }
    .ok { color: #22c55e; }
    .err { color: #ef4444; }
    a {
      color: #93c5fd;
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>VEIS CleanStat</h1>
    <p class="muted">Wallet-based multi-user authentication demo</p>

    <button onclick="connectAndLogin()">Connect MetaMask + Login</button>
    <button onclick="goApp()">Open App</button>
    <button onclick="logout()">Logout</button>

    <h3>Status</h3>
    <pre id="status">Not logged in.</pre>

    <h3>Current User</h3>
    <pre id="user">(none)</pre>

    <h3>Notes</h3>
    <ul>
      <li>Seeded admin wallet for demo: <code>%SEEDED_ADMIN%</code></li>
      <li>Use your own wallet to auto-provision as <code>viewer</code>.</li>
      <li>Promote users via admin endpoint after logging in as seeded admin.</li>
    </ul>
  </div>

<script>
async function connectAndLogin() {
  const status = document.getElementById("status");
  const userBox = document.getElementById("user");

  try {
    if (!window.ethereum) {
      throw new Error("MetaMask not found");
    }

    status.textContent = "Requesting wallet access...";
    const accounts = await window.ethereum.request({
      method: "eth_requestAccounts"
    });

    const wallet = accounts[0];

    status.textContent = "Fetching nonce...";
    const nonceRes = await fetch("/auth/nonce", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({wallet_address: wallet})
    });

    const nonceData = await nonceRes.json();
    if (!nonceRes.ok) {
      throw new Error(JSON.stringify(nonceData));
    }

    status.textContent = "Requesting signature...";
    const signature = await window.ethereum.request({
      method: "personal_sign",
      params: [nonceData.message, wallet]
    });

    status.textContent = "Verifying signature...";
    const verifyRes = await fetch("/auth/verify", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({
        wallet_address: wallet,
        signature: signature
      })
    });

    const authData = await verifyRes.json();
    if (!verifyRes.ok) {
      throw new Error(JSON.stringify(authData));
    }

    localStorage.setItem("access_token", authData.access_token);
    localStorage.setItem("wallet_address", authData.user.wallet_address);
    localStorage.setItem("role", authData.user.role);

    document.cookie = "access_token=" + authData.access_token + "; path=/; SameSite=Lax";

    status.innerHTML = "Login successful. <span class='ok'>Authenticated</span>";
    userBox.textContent = JSON.stringify(authData.user, null, 2);
  } catch (err) {
    status.innerHTML = "<span class='err'>Login failed:</span> " + err.message;
  }
}

function goApp() {
  window.location.href = "/app";
}

async function logout() {
  const token = localStorage.getItem("access_token");

  await fetch("/auth/logout", {
    method: "POST",
    headers: token ? { "Authorization": "Bearer " + token } : {}
  });

  localStorage.removeItem("access_token");
  localStorage.removeItem("wallet_address");
  localStorage.removeItem("role");
  document.cookie = "access_token=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";

  document.getElementById("status").textContent = "Logged out.";
  document.getElementById("user").textContent = "(none)";
}
</script>
</body>
</html>
""".replace("%SEEDED_ADMIN%", SEEDED_ADMIN)


# ============================================================
# GRADIO APP
# ============================================================

def gradio_me(request: gr.Request):
    """
    Get current user inside Gradio.
    """
    fastapi_request = request.request
    token = extract_token_from_request(fastapi_request)
    if not token:
        return {
            "authenticated": False,
            "wallet": None,
            "role": None,
            "organization_id": None,
        }

    try:
        payload = decode_jwt(token)
        wallet = payload["sub"].lower()
        user = USERS.get(wallet)
        if not user:
            raise ValueError("User missing")
        return {
            "authenticated": True,
            "wallet": user["wallet_address"],
            "role": user["role"],
            "organization_id": user.get("organization_id"),
        }
    except Exception:
        return {
            "authenticated": False,
            "wallet": None,
            "role": None,
            "organization_id": None,
        }

def gradio_dashboard(request: gr.Request):
    me = gradio_me(request)
    if not me["authenticated"]:
        return "Not authenticated."

    return (
        f"Authenticated: {me['authenticated']}\n"
        f"Wallet: {me['wallet']}\n"
        f"Role: {me['role']}\n"
        f"Organization: {me['organization_id']}\n\n"
        "Demo City Ops Stats:\n"
        "- Open incidents: 14\n"
        "- Verified cleanups: 52\n"
        "- Hotspot zones: 3\n"
    )

def gradio_admin_list_users(request: gr.Request):
    me = gradio_me(request)
    if not me["authenticated"]:
        return "Not authenticated."
    if me["role"] != "admin":
        return "Forbidden. Admin only."

    rows = []
    for user in USERS.values():
        rows.append(
            f"{user['wallet_address']} | role={user['role']} | "
            f"org={user.get('organization_id')} | status={user.get('status')}"
        )
    return "\n".join(rows) if rows else "No users."

def gradio_admin_set_role(wallet_address: str, role: str, request: gr.Request):
    me = gradio_me(request)
    if not me["authenticated"]:
        return "Not authenticated."
    if me["role"] != "admin":
        return "Forbidden. Admin only."

    try:
        wallet = normalize_wallet(wallet_address)
    except HTTPException as e:
        return f"Error: {e.detail}"

    if role not in VALID_ROLES:
        return f"Invalid role. Choose one of: {', '.join(sorted(VALID_ROLES))}"

    if wallet not in USERS:
        return "User not found."

    USERS[wallet]["role"] = role
    return f"Updated {wallet} to role={role}"


def create_gradio_app():
    """Create Gradio app for VEIS authentication"""
    with gr.Blocks(title=APP_TITLE) as demo:
        gr.Markdown("# VEIS CleanStat")
        gr.Markdown("MetaMask-authenticated multi-user demo app")

        with gr.Tab("Session"):
            session_btn = gr.Button("Refresh Session Info")
            session_out = gr.Textbox(lines=8, label="Session")
            session_btn.click(gradio_dashboard, outputs=session_out)

        with gr.Tab("Admin"):
            gr.Markdown("Admin-only demo controls")
            users_btn = gr.Button("List Users")
            users_out = gr.Textbox(lines=12, label="Users")
            users_btn.click(gradio_admin_list_users, outputs=users_out)

            wallet_in = gr.Textbox(label="Wallet Address")
            role_in = gr.Dropdown(
                choices=sorted(list(VALID_ROLES)),
                value="viewer",
                label="Role"
            )
            role_btn = gr.Button("Set Role")
            role_out = gr.Textbox(label="Result")
            role_btn.click(gradio_admin_set_role, inputs=[wallet_in, role_in], outputs=role_out)

        with gr.Tab("Info"):
            gr.Markdown(
                """
                ### How to use
                1. Open `/` 
                2. Connect MetaMask and sign the nonce
                3. App stores token in cookie/localStorage
                4. Open `/app` 
                5. Refresh Session Info

                ### Demo roles
                - admin
                - city_operator
                - reviewer
                - contractor
                - viewer
                """
            )
    
    return demo
