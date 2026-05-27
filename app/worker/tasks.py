import httpx
import asyncio
from celery import shared_task
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.bill import Bill, BillStatus
from app.services.whatsapp import send_whatsapp_text
from app.services.llm_structurer import structure_ocr_text
from .ocr_engine import clean_and_extract_text
from app.core.config import settings

def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_bill_image(self, bill_id: str, phone_number: str, media_id: str, mime_type: str):
    async def _async_process():
        async with AsyncSessionLocal() as db:
            try:
                print(f"⚙️ Worker starting process for bill {bill_id}")
                result = await db.execute(select(Bill).where(Bill.id == bill_id))
                bill = result.scalar_one_or_none()
                if not bill:
                    raise ValueError(f"Bill not found")

                # 1. DOWNLOAD FROM META
                print("⏳ Downloading media from Meta...")
                meta_url = f"https://graph.facebook.com/v18.0/{media_id}"
                headers = {"Authorization": f"Bearer {settings.WA_ACCESS_TOKEN}"}
                
                async with httpx.AsyncClient() as client:
                    # Get the temporary download URL
                    res_info = await client.get(meta_url, headers=headers)
                    res_info.raise_for_status()
                    download_url = res_info.json().get("url")
                    
                    # Download the actual binary file
                    res_media = await client.get(download_url, headers=headers)
                    res_media.raise_for_status()
                    file_bytes = res_media.content

                print("✅ Downloaded successfully.")

                # 2. UPLOAD TO CLOUDINARY
                print("⏳ Uploading to Cloudinary...")
                from app.services.cloudinary import upload_bill_image
                ext = "pdf" if "pdf" in mime_type else "jpg"
                upload_result = upload_bill_image(file_bytes, f"{bill_id}.{ext}")
                
                bill.cloudinary_public_id = upload_result["public_id"]
                bill.file_url = upload_result["secure_url"]
                
                print("✅ Cloudinary upload complete.")

                # 3. OCR EXTRACTION
                # Note: OpenCV fails natively on PDFs without conversion. We flag it safely.
                if "pdf" in mime_type:
                    raw_text = "PDF format received. Direct extraction pending."
                else:
                    print("⏳ Running PaddleOCR...")
                    raw_text = clean_and_extract_text(file_bytes)
                
                # 4. LLM STRUCTURING
                print("⏳ Running HuggingFace LLM Structure...")
                structured_json = structure_ocr_text(raw_text)

                # 5. SAVE FINAL STATE
                bill.raw_ocr_text = raw_text
                bill.corrected_data = structured_json
                bill.status = BillStatus.REVIEW_PENDING
                await db.commit()
                
                print(f"🎉 SUCCESS! Bill {bill_id} is pending review in dashboard.")

            except Exception as e:
                print(f"❌ Celery Task Failed: {e}")
                await db.rollback()
                try:
                    self.retry(exc=e)
                except self.MaxRetriesExceededError:
                    # Update DB to failed state
                    async with AsyncSessionLocal() as fail_db:
                        fail_result = await fail_db.execute(select(Bill).where(Bill.id == bill_id))
                        failed_bill = fail_result.scalar_one_or_none()
                        if failed_bill:
                            failed_bill.status = BillStatus.OCR_FAILED
                            await fail_db.commit()
                    await send_whatsapp_text(phone_number, "We couldn't process your file. Please make sure it is a clear image and try again.")
                    raise e 
    
    return run_async(_async_process())