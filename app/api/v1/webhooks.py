from fastapi import APIRouter, Depends, Request, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db_session
from app.repositories.merchant_repo import MerchantRepository
from app.repositories.bill_repo import BillRepository
from app.core.redis import check_and_lock_message
from app.worker.tasks import process_bill_image
from app.core.config import settings
from app.core.security import verify_whatsapp_signature
import structlog
from fastapi.responses import JSONResponse

logger = structlog.get_logger()

router = APIRouter()

@router.get("/whatsapp")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == settings.WA_VERIFY_TOKEN:
        logger.info("Webhook verified successfully by Meta")
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/whatsapp")
async def webhook_test(request: Request):
    body = await request.body()

    print("========== WEBHOOK HIT ==========")
    print(body.decode())
    print("=================================")

    return JSONResponse(
        status_code=200,
        content={"status": "received"}
    )