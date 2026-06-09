from beanie.odm.fields import PydanticObjectId
from app.models.bill import Bill
from app.models.enums import BillStatus

class BillRepository:
    def __init__(self, session=None):
        pass

    async def create_bill(self, merchant_id: PydanticObjectId, message_id: str, public_id: str, file_url: str) -> Bill:
        new_bill = Bill(
            merchant_id=merchant_id,
            whatsapp_message_id=message_id,
            cloudinary_public_id=public_id,
            file_url=file_url,
            status=BillStatus.UPLOADED
        )
        await new_bill.insert()
        return new_bill

    async def get_bill_by_id(self, bill_id: str) -> Bill | None:
        try:
            return await Bill.get(PydanticObjectId(bill_id))
        except Exception:
            return None

    async def get_pending_reviews(self, limit: int = 50):
        """Fetches bills for the Next.js ops dashboard."""
        return await Bill.find(Bill.status == BillStatus.REVIEW_PENDING).limit(limit).to_list()

    async def update_bill_review(self, bill_id: str, corrected_data: dict, status: BillStatus, notes: str | None) -> Bill | None:
        """Dashboard endpoint calls this to finalize a bill."""
        bill = await self.get_bill_by_id(bill_id)
        if not bill:
            return None
            
        bill.corrected_data = corrected_data
        bill.status = status
        bill.review_notes = notes
        await bill.save()
        return bill