import httpx
import asyncio
from celery import shared_task
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models.bill import Bill, BillStatus
from app.services.cloudinary import get_signed_url
from app.services.whatsapp import send_whatsapp_text
from app.services.llm_structurer import structure_ocr_text
from .ocr_engine import clean_and_extract_text

def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_bill_image(self, bill_id: str, phone_number: str):
    async def _async_process():
        async with AsyncSessionLocal() as db:
            try:
                # 1. Fetch
                result = await db.execute(select(Bill).where(Bill.id == bill_id))
                bill = result.scalar_one_or_none()
                if not bill:
                    raise ValueError(f"Bill {bill_id} not found")

                # 2. Download Image
                signed_url = get_signed_url(bill.cloudinary_public_id)
                response = httpx.get(signed_url)
                response.raise_for_status()

                # 3. OCR Extraction
                raw_text = clean_and_extract_text(response.content)
                
                # 4. LLM Structuring
                structured_json = structure_ocr_text(raw_text)

                # 5. Update DB State
                bill.raw_ocr_text = raw_text
                bill.corrected_data = structured_json
                bill.status = BillStatus.REVIEW_PENDING
                await db.commit()

            except Exception as e:
                await db.rollback()
                try:
                    self.retry(exc=e)
                except self.MaxRetriesExceededError:
                    # Update DB to failed state using a fresh session
                    async with AsyncSessionLocal() as fail_db:
                        fail_result = await fail_db.execute(select(Bill).where(Bill.id == bill_id))
                        failed_bill = fail_result.scalar_one_or_none()
                        if failed_bill:
                            failed_bill.status = BillStatus.OCR_FAILED
                            await fail_db.commit()
                    
                    await send_whatsapp_text(
                        phone_number, 
                        "We couldn't process your bill image. Please try again."
                    )
                    raise e 
    
    return run_async(_async_process())