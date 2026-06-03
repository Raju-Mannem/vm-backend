import hmac
import hashlib
from fastapi import Request, HTTPException
from app.core.config import settings
import structlog

logger = structlog.get_logger()

async def verify_whatsapp_signature(request: Request):
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature or not signature.startswith("sha256="):
        logger.error("WEBHOOK REJECTED: Missing or invalid signature header")
        raise HTTPException(status_code=403, detail="Missing signature")

    raw_body = await request.body()
    
    expected_hash = hmac.new(
        settings.WA_APP_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature.replace("sha256=", ""), expected_hash):
        logger.error("WEBHOOK REJECTED: Signature Mismatch!", expected=expected_hash, received=signature)
        logger.error("Please double check your WA_APP_SECRET in Render Environment Variables.")
        raise HTTPException(status_code=403, detail="Signature mismatch")

async def verify_evolution_signature(request: Request):
    # Depending on how the Evolution webhook is configured, the secret can be passed as a header
    # e.g., 'apikey' or 'x-custom-webhook-secret'. We'll check standard authorization approaches.
    api_key_header = request.headers.get("apikey")
    custom_secret_header = request.headers.get("x-webhook-secret")
    auth_header = request.headers.get("authorization")

    secret = settings.EVOLUTION_WEBHOOK_SECRET
    
    if not secret:
        # If no secret is configured, bypass the check (for ease of development)
        logger.warning("EVOLUTION_WEBHOOK_SECRET is not set. Skipping webhook verification.")
        return

    is_valid = (
        (api_key_header and api_key_header == secret) or
        (custom_secret_header and custom_secret_header == secret) or
        (auth_header and auth_header == f"Bearer {secret}")
    )

    if not is_valid:
        logger.error("WEBHOOK REJECTED: Evolution API Webhook secret mismatch!")
        raise HTTPException(status_code=403, detail="Evolution Webhook Signature mismatch")