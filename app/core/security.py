import hmac
import hashlib
from fastapi import Request, HTTPException
from app.core.config import settings

async def verify_whatsapp_signature(request: Request):
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature or not signature.startswith("sha256="):
        print("🚨 WEBHOOK REJECTED: Missing or invalid signature header")
        raise HTTPException(status_code=403, detail="Missing signature")

    raw_body = await request.body()
    
    expected_hash = hmac.new(
        settings.WA_APP_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(signature.replace("sha256=", ""), expected_hash):
        print("🚨 WEBHOOK REJECTED: Signature Mismatch!")
        print("👉 Please double check your WA_APP_SECRET in Render Environment Variables.")
        raise HTTPException(status_code=403, detail="Signature mismatch")