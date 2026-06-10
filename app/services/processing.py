import httpx
import asyncio
import json
from tenacity import retry, stop_after_attempt, wait_fixed
from beanie.odm.fields import PydanticObjectId
from app.models.bill import Bill, BillStatus
from app.services.whatsapp import send_whatsapp_text
from app.services.evolution import send_evolution_text, download_evolution_media
from app.services.huggingface import structure_ocr_text
from app.services.cloudinary import upload_bill_image
from app.core.config import settings
import structlog

logger = structlog.get_logger()

@retry(stop=stop_after_attempt(3), wait=wait_fixed(60), reraise=True)
async def _process_bill_image_core(bill_id: str, media_id: str, mime_type: str):
    logger.info("Background task starting process", bill_id=bill_id)
    bill = await Bill.get(PydanticObjectId(bill_id))
    if not bill:
        raise ValueError(f"Bill not found")

    # 1. DOWNLOAD FROM META
    logger.info("Downloading media from Meta", media_id=media_id)
    meta_url = f"https://graph.facebook.com/v18.0/{media_id}"
    headers = {"Authorization": f"Bearer {settings.WA_ACCESS_TOKEN}"}
    
    async with httpx.AsyncClient() as client:
        res_info = await client.get(meta_url, headers=headers)
        if res_info.status_code != 200:
            logger.error("Meta API error response", status=res_info.status_code, body=res_info.text)
        res_info.raise_for_status()
        download_url = res_info.json().get("url")
        
        res_media = await client.get(download_url, headers=headers)
        if res_media.status_code != 200:
            logger.error("Meta Media download error", status=res_media.status_code, body=res_media.text)
        res_media.raise_for_status()
        file_bytes = res_media.content

    logger.info("Downloaded successfully")

    # 2. UPLOAD TO CLOUDINARY
    logger.info("Uploading to Cloudinary")
    ext = "pdf" if "pdf" in mime_type else "jpg"
    
    upload_result = upload_bill_image(file_bytes, f"{bill_id}.{ext}")
    
    bill.cloudinary_public_id = upload_result["public_id"]
    bill.file_url = upload_result["secure_url"]
    
    logger.info("Cloudinary upload and OCR complete", public_id=upload_result["public_id"])

    # 3. OCR EXTRACTION
    raw_text = upload_result.get("raw_text", "")
    if not raw_text:
        if "pdf" in mime_type:
            raw_text = "PDF format received. Direct extraction pending."
        else:
            logger.warning("Cloudinary OCR returned empty text")
    
    # 4. LLM STRUCTURING
    logger.info("Running HuggingFace LLM Structure")
    structured_json_str = structure_ocr_text(raw_text)
    
    try:
        structured_json = json.loads(structured_json_str) if isinstance(structured_json_str, str) else structured_json_str
    except Exception as e:
        logger.error("Failed to parse JSON from LLM", error=str(e))
        structured_json = {}

    # 5. SAVE FINAL STATE
    bill.raw_ocr_text = raw_text
    bill.corrected_data = structured_json
    bill.status = BillStatus.REVIEW_PENDING
    await bill.save()
    
    logger.info("SUCCESS! Bill is pending review in dashboard", bill_id=bill_id)

async def process_bill_image_async(bill_id: str, phone_number: str, media_id: str, mime_type: str):
    try:
        await _process_bill_image_core(bill_id, media_id, mime_type)
    except Exception as e:
        logger.error("Max retries exceeded or fatal error", error=str(e), exc_info=True)
        failed_bill = await Bill.get(PydanticObjectId(bill_id))
        if failed_bill:
            failed_bill.status = BillStatus.OCR_FAILED
            await failed_bill.save()
        await send_whatsapp_text(phone_number, "We couldn't process your file. Please make sure it is a clear image and try again.")


@retry(stop=stop_after_attempt(3), wait=wait_fixed(60), reraise=True)
async def _process_bill_image_evolution_core(bill_id: str, message_dict: dict, mime_type: str):
    logger.info("Background task starting process (Evolution)", bill_id=bill_id)
    bill = await Bill.get(PydanticObjectId(bill_id))
    if not bill:
        raise ValueError(f"Bill not found")

    # 1. DOWNLOAD FROM EVOLUTION API
    logger.info("Downloading media from Evolution API")
    file_bytes = await download_evolution_media(message_dict)
    logger.info("Downloaded successfully")

    # 2. UPLOAD TO CLOUDINARY
    logger.info("Uploading to Cloudinary")
    ext = "pdf" if "pdf" in mime_type else "jpg"
    upload_result = upload_bill_image(file_bytes, f"{bill_id}.{ext}")
    
    bill.cloudinary_public_id = upload_result["public_id"]
    bill.file_url = upload_result["secure_url"]
    
    logger.info("Cloudinary upload and OCR complete", public_id=upload_result["public_id"])

    # 3. OCR EXTRACTION
    raw_text = upload_result.get("raw_text", "")
    if not raw_text:
        if "pdf" in mime_type:
            raw_text = "PDF format received. Direct extraction pending."
        else:
            logger.warning("Cloudinary OCR returned empty text")
    
    # 4. LLM STRUCTURING
    logger.info("Running HuggingFace LLM Structure")
    structured_json_str = structure_ocr_text(raw_text)
    
    try:
        structured_json = json.loads(structured_json_str) if isinstance(structured_json_str, str) else structured_json_str
    except Exception as e:
        logger.error("Failed to parse JSON from LLM", error=str(e))
        structured_json = {}

    # 5. SAVE FINAL STATE
    bill.raw_ocr_text = raw_text
    bill.corrected_data = structured_json
    bill.status = BillStatus.REVIEW_PENDING
    await bill.save()
    
    logger.info("SUCCESS! Bill is pending review in dashboard", bill_id=bill_id)

async def process_bill_image_evolution_async(bill_id: str, phone_number: str, message_dict: dict, mime_type: str):
    try:
        await _process_bill_image_evolution_core(bill_id, message_dict, mime_type)
    except Exception as e:
        logger.error("Max retries exceeded or fatal error (Evolution)", error=str(e), exc_info=True)
        failed_bill = await Bill.get(PydanticObjectId(bill_id))
        if failed_bill:
            failed_bill.status = BillStatus.OCR_FAILED
            await failed_bill.save()
        await send_evolution_text(phone_number, "We couldn't process your file. Please make sure it is a clear image and try again.")