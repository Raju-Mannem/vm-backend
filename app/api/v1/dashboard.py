from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from app.db.session import get_db_session
from app.repositories.bill_repo import BillRepository
from app.models.enums import BillStatus

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

class BillReviewUpdate(BaseModel):
    corrected_data: str 
    status: BillStatus
    review_notes: str | None = None

@router.get("/bills/pending")
async def get_pending_bills(db: AsyncSession = Depends(get_db_session)):
    repo = BillRepository(db)
    bills = await repo.get_pending_reviews(limit=50)
    return {"data": bills}

@router.post("/bills/{bill_id}/review")
async def submit_bill_review(
    bill_id: str, 
    payload: BillReviewUpdate, 
    db: AsyncSession = Depends(get_db_session)
):
    """Saves the corrected LLM/Human data and marks the bill as Approved/Rejected."""
    if payload.status not in [BillStatus.APPROVED, BillStatus.REJECTED]:
        raise HTTPException(status_code=400, detail="Invalid final status")

    repo = BillRepository(db)
    
    # Use the new repository method to handle the transaction safely
    bill = await repo.update_bill_review(
        bill_id=bill_id,
        corrected_data=payload.corrected_data,
        status=payload.status,
        notes=payload.review_notes
    )
    
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")
    
    # TODO: In future, dispatch a Celery task here to send final summary to merchant 
    
    return {"status": "success", "bill_id": bill_id}