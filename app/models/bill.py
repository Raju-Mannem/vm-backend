from typing import Annotated, Optional, Dict, Any
from datetime import datetime, timezone

from pydantic import Field
from beanie import Document, Indexed
from beanie.odm.fields import PydanticObjectId

from .enums import BillStatus


class Bill(Document):
    merchant_id: Annotated[PydanticObjectId, Indexed()]
    whatsapp_message_id: Annotated[str, Indexed(unique=True)]

    cloudinary_public_id: str
    file_url: str

    status: BillStatus = BillStatus.UPLOADED

    raw_ocr_text: Optional[str] = None
    corrected_data: Optional[Dict[str, Any]] = None
    review_notes: Optional[str] = None

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: Optional[datetime] = None

    class Settings:
        name = "bills"