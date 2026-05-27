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