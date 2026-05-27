from fastapi import APIRouter, Depends, Request, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db_session
from app.repositories.merchant_repo import MerchantRepository
from app.repositories.bill_repo import BillRepository
from app.core.redis import check_and_lock_message
from app.worker.tasks import process_bill_image
from app.core.config import settings
from app.core.security import verify_whatsapp_signature

router = APIRouter()

@router.get("/whatsapp")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    if mode == "subscribe" and token == settings.WA_VERIFY_TOKEN:
        print("✅ Webhook verified successfully by Meta!")
        return Response(content=challenge, media_type="text/plain")
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/whatsapp", dependencies=[Depends(verify_whatsapp_signature)])
async def handle_whatsapp_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
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

        # 1. REDIS IDEMPOTENCY
        if not await check_and_lock_message(message_id):
            print(f"⏩ Skipping duplicate message {message_id}")
            return {"status": "already processed"} 

        merchant_repo = MerchantRepository(db)
        bill_repo = BillRepository(db)
        merchant = await merchant_repo.upsert_merchant(whatsapp_id, name)

        # 2. ROUTING LOGIC: Handle both direct images and file attachments (documents)
        if msg_type in ["image", "document"]:
            media_data = message.get(msg_type, {})
            media_id = media_data.get("id")
            mime_type = media_data.get("mime_type", "image/jpeg")
            
            print(f"📥 Received {msg_type} from {name} (Media ID: {media_id})")
            
            bill = await bill_repo.create_bill(
                merchant_id=merchant.id,
                message_id=message_id,
                public_id=f"pending_{media_id}", 
                file_url="pending" 
            )
            
            # Dispatch to Celery Queue WITH the extra arguments
            process_bill_image.delay(bill.id, whatsapp_id, media_id, mime_type)
            return {"status": "success - media queued"}
            
        elif msg_type == "text":
            text_body = message.get("text", {}).get("body", "")
            print(f"💬 Received text from {name}: {text_body}")
            return {"status": "success - text received"}
            
        else:
            print(f"⚠️ Ignored unsupported message type: {msg_type}")
            return {"status": "ignored - unsupported media"}

    except Exception as e:
        print(f"❌ Error parsing webhook: {e}")
        return {"status": "error parsing payload"}