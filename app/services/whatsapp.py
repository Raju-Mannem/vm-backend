import httpx
from app.core.config import settings

async def send_whatsapp_text(phone_number: str, message: str):
    """Sends a text message via Meta Cloud API."""
    url = f"https://graph.facebook.com/v18.0/{settings.WA_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {settings.WA_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {"body": message}
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()