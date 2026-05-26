from pydantic import BaseModel

class WebhookPayload(BaseModel):
    whatsapp_id: str
    name: str | None = None
    message_id: str
    cloudinary_id: str
    secure_url: str