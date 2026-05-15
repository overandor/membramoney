from typing import Optional
from src.db.database import get_connection, now_iso, generate_id
from src.models.enums import PaymentStatus, VisitStatus
from src.models.schemas import PaymentQuote, PaymentAuthorize, PaymentOut, PayoutRelease
from src.core.exceptions import PaymentError
from src.services.reservations import get_visit

PLATFORM_FEE_BPS = 1500  # 15.00%

def calculate_quote(visit_id: str) -> PaymentQuote:
    visit = get_visit(visit_id)
    if not visit:
        raise PaymentError("Visit not found")

    from src.services.assets import get_asset
    asset = get_asset(visit.asset_id)
    if not asset:
        raise PaymentError("Asset not found")

    subtotal = asset.price_cents
    insurance_premium = int(subtotal * 0.07)  # 7% placeholder
    platform_fee = int(subtotal * PLATFORM_FEE_BPS / 10000)
    deposit = asset.deposit_cents
    total = subtotal + insurance_premium + platform_fee + deposit

    return PaymentQuote(
        visit_id=visit_id,
        subtotal_cents=subtotal,
        insurance_premium_cents=insurance_premium,
        platform_fee_cents=platform_fee,
        deposit_cents=deposit,
        total_cents=total,
    )

def authorize_payment(data: PaymentAuthorize) -> PaymentOut:
    visit = get_visit(data.visit_id)
    if not visit:
        raise PaymentError("Visit not found")
    if visit.status != VisitStatus.insurance_quoted:
        raise PaymentError(f"Cannot authorize payment from status {visit.status}")

    quote = calculate_quote(data.visit_id)
    payment_id = generate_id("pay_")

    # Simulate provider payment intent creation
    provider_intent_id = f"pi_{generate_id()}"

    conn = get_connection()
    conn.execute(
        """
        INSERT INTO payments (payment_id, visit_id, guest_id, host_id, provider, provider_payment_intent_id,
            status, subtotal_cents, insurance_premium_cents, platform_fee_cents, deposit_cents,
            total_authorized_cents, currency, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            payment_id, data.visit_id, visit.guest_id, visit.host_id, data.provider, provider_intent_id,
            PaymentStatus.authorized.value, quote.subtotal_cents, quote.insurance_premium_cents,
            quote.platform_fee_cents, quote.deposit_cents, quote.total_cents, "USD", now_iso(), now_iso(),
        ),
    )
    conn.commit()
    conn.close()

    # Advance reservation status
    from src.services.reservations import update_visit_status
    update_visit_status(data.visit_id, VisitStatus.payment_authorized)

    return get_payment(payment_id)

def capture_payment(visit_id: str) -> PaymentOut:
    visit = get_visit(visit_id)
    if not visit:
        raise PaymentError("Visit not found")
    if visit.status not in (VisitStatus.checked_out, VisitStatus.completed):
        raise PaymentError(f"Cannot capture from status {visit.status}")

    payment = get_payment_by_visit(visit_id)
    if not payment:
        raise PaymentError("Payment not found")
    if payment.status != PaymentStatus.authorized:
        raise PaymentError(f"Payment status is {payment.status}, expected authorized")

    conn = get_connection()
    conn.execute(
        "UPDATE payments SET status = ?, total_captured_cents = total_authorized_cents, updated_at = ? WHERE payment_id = ?",
        (PaymentStatus.captured.value, now_iso(), payment.payment_id),
    )
    conn.commit()
    conn.close()
    return get_payment(payment.payment_id)

def refund_payment(visit_id: str) -> PaymentOut:
    payment = get_payment_by_visit(visit_id)
    if not payment:
        raise PaymentError("Payment not found")
    if payment.status != PaymentStatus.authorized:
        raise PaymentError("Can only refund authorized payments")

    conn = get_connection()
    conn.execute(
        "UPDATE payments SET status = ?, updated_at = ? WHERE payment_id = ?",
        (PaymentStatus.refunded.value, now_iso(), payment.payment_id),
    )
    conn.commit()
    conn.close()
    return get_payment(payment.payment_id)

def release_payout(data: PayoutRelease) -> PaymentOut:
    payment = get_payment(data.payment_id)
    if not payment:
        raise PaymentError("Payment not found")
    if payment.status != PaymentStatus.captured:
        raise PaymentError("Can only release payout on captured payments")
    # In production: call Stripe Connect / payout API
    return payment

def get_payment(payment_id: str) -> Optional[PaymentOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM payments WHERE payment_id = ?", (payment_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_payment(row)

def get_payment_by_visit(visit_id: str) -> Optional[PaymentOut]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM payments WHERE visit_id = ?", (visit_id,)).fetchone()
    conn.close()
    if not row:
        return None
    return _row_to_payment(row)

def _row_to_payment(row: dict) -> PaymentOut:
    return PaymentOut(
        payment_id=row["payment_id"],
        visit_id=row["visit_id"],
        guest_id=row["guest_id"],
        host_id=row["host_id"],
        provider=row["provider"],
        provider_payment_intent_id=row["provider_payment_intent_id"],
        status=PaymentStatus(row["status"]),
        subtotal_cents=row["subtotal_cents"],
        insurance_premium_cents=row["insurance_premium_cents"],
        platform_fee_cents=row["platform_fee_cents"],
        deposit_cents=row["deposit_cents"],
        total_authorized_cents=row["total_authorized_cents"],
        total_captured_cents=row["total_captured_cents"],
        currency=row["currency"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
