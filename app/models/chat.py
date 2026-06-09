from typing import Annotated
from datetime import datetime, timezone

from pydantic import Field
from beanie import Document, Indexed
from beanie.odm.fields import PydanticObjectId


class ChatMessage(Document):
    merchant_id: Annotated[PydanticObjectId, Indexed()]

    role: str  # "user", "assistant", or "system"
    content: str

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    class Settings:
        name = "chat_history"