from typing import Optional, Dict, Any
from datetime import datetime, timezone
from pydantic import Field
from beanie import Document, Indexed
from beanie.odm.fields import PydanticObjectId
from .enums import BillStatus

class Bill(Document):
    merchant_id: Indexed(PydanticObjectId)
    whatsapp_message_id: Indexed(str, unique=True)
    
    # Storage
    cloudinary_public_id: str
    file_url: str
    
    # State Machine
    status: BillStatus = BillStatus.UPLOADED
    
    # OCR & Review Data
    raw_ocr_text: Optional[str] = None
    corrected_data: Optional[Dict[str, Any]] = None  # Using Dict instead of JSON string
    review_notes: Optional[str] = None
    
    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None
    
    class Settings:
        name = "bills"