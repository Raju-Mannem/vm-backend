import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.bill import Bill
from app.models.enums import BillStatus

class BillRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_bill(self, merchant_id: str, message_id: str, public_id: str, file_url: str) -> Bill:
        new_bill = Bill(
            id=str(uuid.uuid4()),
            merchant_id=merchant_id,
            whatsapp_message_id=message_id,
            cloudinary_public_id=public_id,
            file_url=file_url,
            status=BillStatus.UPLOADED
        )
        self.session.add(new_bill)
        await self.session.commit()
        await self.session.refresh(new_bill)
        return new_bill

    async def get_bill_by_id(self, bill_id: str) -> Bill | None:
        result = await self.session.execute(select(Bill).where(Bill.id == bill_id))
        return result.scalar_one_or_none()

    async def get_pending_reviews(self, limit: int = 50):
        """Fetches bills for the Next.js ops dashboard."""
        stmt = select(Bill).where(Bill.status == BillStatus.REVIEW_PENDING).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update_bill_review(self, bill_id: str, corrected_data: str, status: BillStatus, notes: str | None) -> Bill | None:
        """Dashboard endpoint calls this to finalize a bill."""
        stmt = (
            update(Bill)
            .where(Bill.id == bill_id)
            .values(
                corrected_data=corrected_data,
                status=status,
                review_notes=notes
            )
            .returning(Bill)
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one_or_none()