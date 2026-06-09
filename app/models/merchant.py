from typing import Annotated, Optional
from datetime import datetime, timezone

from beanie import Document, Indexed
from pydantic import Field

class Merchant(Document):
    whatsapp_id: Annotated[str, Indexed(unique=True)]

    name: Optional[str] = "Unknown"
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    class Settings:
        name = "merchants"