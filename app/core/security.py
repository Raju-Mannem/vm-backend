import hmac
import hashlib
from fastapi import Request, HTTPException, Security
from app.core.config import settings

async def verify_whatsapp_signature(request: Request):
    """
    Validates the X-Hub-Signature-256 header sent by Meta.
    Fails the request immediately with a 403 if tampering is detected.
    """
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature or not signature.startswith("sha256="):
        raise HTTPException(status_code=403, detail="Missing or invalid signature header")

    # MUST read the raw body for accurate HMAC calculation
    raw_body = await request.body()
    
    # Calculate the expected signature using Meta App Secret
    expected_hash = hmac.new(
        settings.WA_APP_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    # Use secure string comparison to prevent timing attacks
    if not hmac.compare_digest(signature.replace("sha256=", ""), expected_hash):
        raise HTTPException(status_code=403, detail="Signature mismatch")