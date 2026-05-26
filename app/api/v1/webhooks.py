from fastapi import APIRouter, Depends, Query, Response, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db_session
from app.repositories.merchant_repo import MerchantRepository
from app.repositories.bill_repo import BillRepository
from app.schemas.webhook import WebhookPayload
from app.worker.tasks import process_bill_image
from app.core.config import settings

router = APIRouter()

@router.get("/whatsapp")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """
    Handle Meta's Webhook verification challenge (GET request).
    """
    # TIP: Move this to your app.core.config.settings later
    # This must match EXACTLY what you type into the Meta Dashboard
    VERIFY_TOKEN = settings.WA_VERIFY_TOKEN

    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        # Meta requires returning ONLY the hub.challenge as plain text
        return Response(content=hub_challenge, media_type="text/plain")
    
    return Response(content="Verification failed", status_code=403)

@router.post("/whatsapp")
async def handle_whatsapp_webhook(
    payload: WebhookPayload,
    db: AsyncSession = Depends(get_db_session)
):
    if not await check_and_lock_message(payload.message_id):
        return {"status": "already processed"}
        
    merchant_repo = MerchantRepository(db)
    bill_repo = BillRepository(db)
        
    # save data
    merchant = await merchant_repo.upsert_merchant(payload.whatsapp_id, payload.name)
    
    bill = await bill_repo.create_bill(
        merchant_id=merchant.id,
        message_id=payload.message_id,
        public_id=payload.cloudinary_id,
        file_url=payload.secure_url
    )
        
    # Send to Celery worker handled in the background via Redis
    process_bill_image.delay(bill.id, payload.whatsapp_id)
    
    return {"status": "success"}