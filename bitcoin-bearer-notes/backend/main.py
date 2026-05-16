"""CoinPack Redemption API - FastAPI Application."""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import base64
import hmac
import structlog
import time

from core.config import settings
from models.database import init_db
from api.routes import router

logger = structlog.get_logger()

ADMIN_MUTATION_PATH_SUFFIXES = (
    "/process",
    "/mark-paid",
    "/reject",
    "/expire",
    "/snapshot",
)

WALLET_MUTATION_PATH_SUFFIXES = (
    "/transfer",
    "/burn-to-redeem",
)

SIGNATURE_MAX_AGE_SECONDS = 300


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("Starting CoinPack API", version="0.1.0", env=settings.ENV)

    # Fail fast on insecure production configuration.
    settings.validate_production_security()

    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down CoinPack API")


def _is_admin_mutation(path: str, method: str) -> bool:
    if method.upper() != "POST":
        return False
    return (
        path.startswith("/api/v1/redemptions/") and path.endswith(ADMIN_MUTATION_PATH_SUFFIXES[:3])
    ) or (
        path.startswith("/api/v1/coinpacks/") and path.endswith("/expire")
    ) or path == "/api/v1/reserves/snapshot"


def _is_wallet_mutation(path: str, method: str) -> bool:
    return (
        method.upper() == "POST"
        and path.startswith("/api/v1/notes/")
        and path.endswith(WALLET_MUTATION_PATH_SUFFIXES)
    )


def _admin_authorized(request: Request) -> bool:
    expected = settings.ADMIN_API_TOKEN
    provided = request.headers.get("X-Admin-Token") or ""
    if not expected:
        return False
    return hmac.compare_digest(provided, expected)


def _verify_solana_wallet_signature(wallet: str, message: str, signature_b64: str) -> bool:
    """Verify a Phantom/Solflare signMessage signature.

    The message must be UTF-8, include method/path/timestamp, and be signed by the
    submitted base58 Solana wallet. The signature header is base64-encoded bytes.
    """
    try:
        from solders.pubkey import Pubkey
        from solders.signature import Signature

        pubkey = Pubkey.from_string(wallet)
        signature = Signature.from_bytes(base64.b64decode(signature_b64, validate=True))
        return bool(signature.verify(pubkey, message.encode("utf-8")))
    except Exception as exc:
        logger.warning("wallet_signature_verify_failed", error=str(exc))
        return False


def _wallet_authorized(request: Request) -> bool:
    wallet = request.headers.get("X-Wallet-Address") or ""
    message = request.headers.get("X-Wallet-Message") or ""
    signature = request.headers.get("X-Wallet-Signature") or ""

    if not wallet or not message or not signature:
        return False
    if f"method={request.method.upper()}" not in message:
        return False
    if f"path={request.url.path}" not in message:
        return False

    timestamp_line = next((line for line in message.split("\n") if line.startswith("timestamp=")), None)
    if not timestamp_line:
        return False
    try:
        signed_at = int(timestamp_line.split("=", 1)[1])
    except ValueError:
        return False
    if abs(int(time.time()) - signed_at) > SIGNATURE_MAX_AGE_SECONDS:
        return False

    return _verify_solana_wallet_signature(wallet, message, signature)


app = FastAPI(
    title="CoinPack Redemption API",
    description="Bitcoin-backed denominated bearer notes on Solana",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Admin-Token",
        "X-Wallet-Address",
        "X-Wallet-Message",
        "X-Wallet-Signature",
    ],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)


@app.middleware("http")
async def security_gate_middleware(request: Request, call_next):
    """Reject privileged or holder-mutating calls before route handlers run."""
    path = request.url.path

    if _is_admin_mutation(path, request.method) and not _admin_authorized(request):
        return JSONResponse(
            status_code=401,
            content={"error": "admin_auth_required", "message": "Valid X-Admin-Token required"},
        )

    if _is_wallet_mutation(path, request.method) and not _wallet_authorized(request):
        return JSONResponse(
            status_code=401,
            content={
                "error": "wallet_signature_required",
                "message": "Valid X-Wallet-Address, X-Wallet-Message, and X-Wallet-Signature headers required",
            },
        )

    return await call_next(request)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    """Request/response logging."""
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    logger.info(
        "request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=round(duration * 1000, 2),
        client_ip=request.client.host if request.client else None,
    )
    return response


# Error handlers
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "message": "An unexpected error occurred"},
    )


# Routes
app.include_router(router)


@app.get("/")
async def root():
    return {
        "service": "CoinPack Redemption API",
        "version": "0.1.0",
        "description": "Bitcoin-backed denominated bearer notes on Solana",
        "docs": "/docs" if settings.DEBUG else None,
        "endpoints": {
            "health": "/api/v1/health",
            "notes": "/api/v1/notes",
            "claims": "/api/v1/claims",
            "reserves": "/api/v1/reserves",
            "stats": "/api/v1/stats",
        },
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )
