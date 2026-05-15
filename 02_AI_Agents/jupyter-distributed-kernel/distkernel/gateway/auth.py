"""
Wallet-based authentication for the distributed notebook.
MetaMask signs a challenge; wallet address = user identity / API key.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Any, Dict, Optional, Tuple

log = logging.getLogger("distkernel.auth")

# In-memory stores (production would use a DB)
_challenges: Dict[str, Dict[str, Any]] = {}   # nonce → {address, ts, used}
_sessions: Dict[str, Dict[str, Any]] = {}      # token → {address, ts, name}
_users: Dict[str, Dict[str, Any]] = {}          # address → {name, joined, cells_run, ...}

SESSION_TTL = 86400  # 24 hours


def create_challenge(address: str) -> Dict[str, str]:
    """Generate a challenge nonce for a wallet address to sign."""
    address = address.lower().strip()
    nonce = secrets.token_hex(16)
    message = f"Sign in to DistKernel Notebook\nNonce: {nonce}\nTimestamp: {int(time.time())}"
    _challenges[nonce] = {
        "address": address,
        "message": message,
        "ts": time.time(),
        "used": False,
    }
    # Expire old challenges
    _expire_challenges()
    return {"nonce": nonce, "message": message}


def verify_signature(address: str, nonce: str, signature: str) -> Tuple[bool, str]:
    """
    Verify wallet signature. Returns (success, session_token_or_error).

    For the demo, we trust the client-side MetaMask verification.
    The signature is stored as the proof. In production, use eth_account
    to recover the signer address from the signature.
    """
    address = address.lower().strip()
    challenge = _challenges.get(nonce)

    if not challenge:
        return False, "Invalid or expired nonce"
    if challenge["used"]:
        return False, "Nonce already used"
    if challenge["address"] != address:
        return False, "Address mismatch"
    if time.time() - challenge["ts"] > 300:  # 5 min expiry
        return False, "Challenge expired"
    if not signature or len(signature) < 10:
        return False, "Invalid signature"

    # Mark used
    challenge["used"] = True

    # Create session
    token = secrets.token_hex(32)
    _sessions[token] = {
        "address": address,
        "ts": time.time(),
        "signature": signature,
    }

    # Register/update user
    if address not in _users:
        _users[address] = {
            "address": address,
            "name": f"{address[:6]}...{address[-4:]}",
            "joined": time.time(),
            "cells_run": 0,
            "last_active": time.time(),
            "compute_contributed": 0,
        }
    _users[address]["last_active"] = time.time()

    short = f"{address[:6]}...{address[-4:]}"
    log.info("User authenticated: %s", short)
    return True, token


def validate_session(token: str) -> Optional[Dict[str, Any]]:
    """Check if a session token is valid. Returns user info or None."""
    session = _sessions.get(token)
    if not session:
        return None
    if time.time() - session["ts"] > SESSION_TTL:
        _sessions.pop(token, None)
        return None
    address = session["address"]
    user = _users.get(address)
    if not user:
        return None
    user["last_active"] = time.time()
    return user


def get_all_users() -> list:
    """Return all registered users (for participant list)."""
    now = time.time()
    return [
        {**u, "online": (now - u["last_active"]) < 120}
        for u in _users.values()
    ]


def record_cell_run(address: str) -> None:
    """Increment cell count for a user."""
    user = _users.get(address.lower())
    if user:
        user["cells_run"] = user.get("cells_run", 0) + 1
        user["last_active"] = time.time()


def _expire_challenges() -> None:
    now = time.time()
    stale = [k for k, v in _challenges.items() if now - v["ts"] > 300]
    for k in stale:
        _challenges.pop(k, None)
