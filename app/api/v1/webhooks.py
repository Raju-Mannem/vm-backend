from fastapi import APIRouter, Depends, Request, HTTPException, Response, BackgroundTasks
from pymongo.errors import DuplicateKeyError
from app.repositories.merchant_repo import MerchantRepository
from app.repositories.bill_repo import BillRepository
from app.services.processing import process_bill_image_async, process_bill_image_evolution_async
from app.services.agent import respond_to_user_async
from app.core.config import settings
from app.core.security import verify_whatsapp_signature, verify_evolution_signature
from app.models.bill import Bill
import structlog

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

@router.post("/whatsapp", dependencies=[Depends(verify_whatsapp_signature)])
async def handle_whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    payload = await request.json()
    
    try:
        entry = payload.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})
        
        if "messages" not in value:
            return {"status": "ignored - not a message"}

        message = value["messages"][0]
        contact = value.get("contacts", [{}])[0].get("profile", {})
        
        whatsapp_id = message.get("from")
        name = contact.get("name", "Unknown")
        message_id = message.get("id")
        msg_type = message.get("type")

        # 1. DB IDEMPOTENCY
        existing_bill = await Bill.find_one(Bill.whatsapp_message_id == message_id)
        if existing_bill:
            logger.info("Skipping duplicate message", message_id=message_id)
            return {"status": "already processed"}

        merchant_repo = MerchantRepository()
        bill_repo = BillRepository()
        merchant = await merchant_repo.upsert_merchant(whatsapp_id, name)

        # 2. ROUTING LOGIC: Handle both direct images and file attachments (documents)
        if msg_type in ["image", "document"]:
            media_data = message.get(msg_type, {})
            media_id = media_data.get("id")
            mime_type = media_data.get("mime_type", "image/jpeg")
            
            logger.info("Received media", msg_type=msg_type, name=name, media_id=media_id)
            
            try:
                bill = await bill_repo.create_bill(
                    merchant_id=merchant.id,
                    message_id=message_id,
                    public_id=f"pending_{media_id}", 
                    file_url="pending" 
                )
            except DuplicateKeyError:
                logger.info("Skipping duplicate message during race condition", message_id=message_id)
                return {"status": "already processed"}
            
            # Dispatch to FastAPI BackgroundTasks
            background_tasks.add_task(process_bill_image_async, str(bill.id), whatsapp_id, media_id, mime_type)
            return {"status": "success - media queued"}
            
        elif msg_type == "text":
            text_body = message.get("text", {}).get("body", "")
            logger.info("Received text", name=name, text_body=text_body)
            background_tasks.add_task(respond_to_user_async, str(merchant.id), "whatsapp", whatsapp_id, text_body)
            return {"status": "success - text received"}
            
        else:
            logger.warning("Ignored unsupported message type", msg_type=msg_type)
            return {"status": "ignored - unsupported media"}

    except Exception as e:
        logger.error("Error parsing webhook", error=str(e), exc_info=True)
        return {"status": "error parsing payload"}

@router.post("/evolution", dependencies=[Depends(verify_evolution_signature)])
async def handle_evolution_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    payload = await request.json()
    
    try:
        event = payload.get("event")
        if event != "messages.upsert":
            return {"status": "ignored - not a message event"}

        data = payload.get("data", {})
        key = data.get("key", {})
        
        if key.get("fromMe"):
            return {"status": "ignored - from me"}

        whatsapp_id = key.get("remoteJid", "").split("@")[0]
        name = data.get("pushName", "Unknown")
        message_id = key.get("id")
        msg_type = data.get("messageType")

        if not message_id:
            return {"status": "ignored - no message id"}

        # 1. DB IDEMPOTENCY
        existing_bill = await Bill.find_one(Bill.whatsapp_message_id == message_id)
        if existing_bill:
            logger.info("Skipping duplicate message", message_id=message_id)
            return {"status": "already processed"}

        merchant_repo = MerchantRepository()
        bill_repo = BillRepository()
        merchant = await merchant_repo.upsert_merchant(whatsapp_id, name)

        if msg_type in ["imageMessage", "documentMessage"]:
            logger.info("Received evolution media", msg_type=msg_type, name=name, message_id=message_id)
            
            try:
                bill = await bill_repo.create_bill(
                    merchant_id=merchant.id,
                    message_id=message_id,
                    public_id=f"pending_evo_{message_id}", 
                    file_url="pending"
                )
            except DuplicateKeyError:
                logger.info("Skipping duplicate message during race condition", message_id=message_id)
                return {"status": "already processed"}
            
            background_tasks.add_task(process_bill_image_evolution_async, str(bill.id), whatsapp_id, data, "image/jpeg")
            return {"status": "success - media queued"}
            
        elif msg_type in ["conversation", "extendedTextMessage"]:
            text_body = ""
            if msg_type == "conversation":
                text_body = data.get("message", {}).get("conversation", "")
            else:
                text_body = data.get("message", {}).get("extendedTextMessage", {}).get("text", "")
                
            logger.info("Received text", name=name, text_body=text_body)
            background_tasks.add_task(respond_to_user_async, str(merchant.id), "evolution", whatsapp_id, text_body)
            return {"status": "success - text received"}
            
        else:
            logger.warning("Ignored unsupported message type", msg_type=msg_type)
            return {"status": "ignored - unsupported media"}

    except Exception as e:
        logger.error("Error parsing evolution webhook", error=str(e), exc_info=True)
        return {"status": "error parsing payload"}