from app.core.config import get_settings

settings = get_settings()

# Stripe is optional; gracefully degrade if not configured
try:
    import stripe
    stripe.api_key = settings.stripe_secret_key
    STRIPE_AVAILABLE = True
except Exception:
    STRIPE_AVAILABLE = False

def create_payment_intent(amount_cents: int, currency: str = "usd", customer_id: str | None = None, metadata: dict | None = None):
    if not STRIPE_AVAILABLE:
        return {"error": "Stripe not configured"}
    return stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=currency,
        customer=customer_id,
        metadata=metadata or {},
        automatic_payment_methods={"enabled": True},
    )

def capture_payment_intent(payment_intent_id: str):
    if not STRIPE_AVAILABLE:
        return {"error": "Stripe not configured"}
    return stripe.PaymentIntent.capture(payment_intent_id)

def create_connected_account(email: str):
    if not STRIPE_AVAILABLE:
        return {"error": "Stripe not configured"}
    return stripe.Account.create(
        type="express",
        email=email,
        capabilities={
            "transfers": {"requested": True},
        },
    )

def create_account_link(account_id: str, refresh_url: str, return_url: str):
    if not STRIPE_AVAILABLE:
        return {"error": "Stripe not configured"}
    return stripe.AccountLink.create(
        account=account_id,
        refresh_url=refresh_url,
        return_url=return_url,
        type="account_onboarding",
    )

def create_transfer(amount_cents: int, destination_account_id: str, metadata: dict | None = None):
    if not STRIPE_AVAILABLE:
        return {"error": "Stripe not configured"}
    return stripe.Transfer.create(
        amount=amount_cents,
        currency="usd",
        destination=destination_account_id,
        metadata=metadata or {},
    )
