"""Security primitives for signed API requests, replay prevention, and audit integrity."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from models.database import AuditLog, RequestNonce


def sha256_hex(value: str | bytes) -> str:
    data = value.encode("utf-8") if isinstance(value, str) else value
    return hashlib.sha256(data).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def parse_signed_message(message: str) -> dict[str, str]:
    """Parse newline-delimited key=value wallet messages."""
    parsed: dict[str, str] = {}
    for line in message.splitlines():
        if "=" in line:
            key, val = line.split("=", 1)
            parsed[key.strip()] = val.strip()
    return parsed


async def consume_nonce(
    db: AsyncSession,
    *,
    wallet_address: str,
    nonce: str,
    method: str,
    path: str,
    message: str,
    ttl_seconds: int = 300,
) -> bool:
    """Persist a nonce exactly once. Returns False on replay."""
    now = datetime.now(timezone.utc)
    record = RequestNonce(
        wallet_address=wallet_address,
        nonce=nonce,
        method=method.upper(),
        path=path,
        message_hash=sha256_hex(message),
        used_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    db.add(record)
    try:
        await db.commit()
        return True
    except IntegrityError:
        await db.rollback()
        return False


async def append_audit_log(
    db: AsyncSession,
    *,
    event_type: str,
    wallet_address: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict[str, Any] | None = None,
    signer: str | None = None,
) -> AuditLog:
    """Append tamper-evident audit event using a hash chain."""
    latest = await db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(1))
    prev = latest.scalar_one_or_none()
    previous_hash = prev.event_hash if prev else None
    payload = {
        "event_type": event_type,
        "wallet_address": wallet_address,
        "ip_address": ip_address,
        "user_agent": user_agent,
        "details": details or {},
        "previous_hash": previous_hash,
        "signer": signer,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    event_hash = sha256_hex(canonical_json(payload))
    audit = AuditLog(
        event_type=event_type,
        wallet_address=wallet_address,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details or {},
        previous_hash=previous_hash,
        event_hash=event_hash,
        signer=signer,
    )
    db.add(audit)
    await db.commit()
    await db.refresh(audit)
    return audit


async def verify_audit_chain(db: AsyncSession, limit: int = 1000) -> dict[str, Any]:
    """Basic continuity check for recent audit records."""
    result = await db.execute(select(AuditLog).order_by(AuditLog.id.asc()).limit(limit))
    events = result.scalars().all()
    previous_hash = None
    broken_at: int | None = None
    for event in events:
        if event.previous_hash != previous_hash:
            broken_at = event.id
            break
        previous_hash = event.event_hash
    return {
        "checked": len(events),
        "valid_chain": broken_at is None,
        "broken_at": broken_at,
        "head_hash": previous_hash,
    }
