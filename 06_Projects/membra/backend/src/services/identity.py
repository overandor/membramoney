from typing import Optional
from src.db.database import get_connection, now_iso, generate_id
from src.models.enums import IdentityLevel, UserType
from src.models.schemas import UserCreate, UserOut, IdentityVerifyOut
from src.core.exceptions import IdentityError

def create_user(data: UserCreate) -> UserOut:
    conn = get_connection()
    user_id = generate_id("usr_")
    try:
        conn.execute(
            """
            INSERT INTO users (user_id, email, name, phone, user_type, identity_level, trust_score, blocked, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, data.email, data.name, data.phone, data.user_type.value, IdentityLevel.unverified.value, 0.5, 0, now_iso()),
        )
        conn.commit()
    except Exception as e:
        raise IdentityError(f"Failed to create user: {e}")
    finally:
        conn.close()
    return get_user(user_id)

def get_user(user_id: str) -> Optional[UserOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return UserOut(
        user_id=row["user_id"],
        email=row["email"],
        name=row["name"],
        phone=row["phone"],
        user_type=UserType(row["user_type"]),
        identity_level=IdentityLevel(row["identity_level"]),
        trust_score=row["trust_score"],
        blocked=bool(row["blocked"]),
        created_at=row["created_at"],
    )

def verify_identity(user_id: str, document_type: str = "passport") -> IdentityVerifyOut:
    user = get_user(user_id)
    if not user:
        raise IdentityError("User not found")
    if user.blocked:
        raise IdentityError("User is blocked")

    # Simulate identity verification flow
    new_level = IdentityLevel.id_verified
    conn = get_connection()
    conn.execute(
        "UPDATE users SET identity_level = ?, trust_score = ? WHERE user_id = ?",
        (new_level.value, 0.85, user_id),
    )
    conn.commit()
    conn.close()

    return IdentityVerifyOut(
        user_id=user_id,
        identity_level=new_level,
        verified_at=now_iso(),
    )

def list_users(user_type: Optional[UserType] = None) -> list[UserOut]:
    conn = get_connection()
    if user_type:
        rows = conn.execute("SELECT * FROM users WHERE user_type = ?", (user_type.value,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return [_row_to_user(r) for r in rows]

def _row_to_user(row: dict) -> UserOut:
    return UserOut(
        user_id=row["user_id"],
        email=row["email"],
        name=row["name"],
        phone=row["phone"],
        user_type=UserType(row["user_type"]),
        identity_level=IdentityLevel(row["identity_level"]),
        trust_score=row["trust_score"],
        blocked=bool(row["blocked"]),
        created_at=row["created_at"],
    )
