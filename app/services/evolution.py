import httpx
import base64
from app.core.config import settings
import structlog

logger = structlog.get_logger()

def get_evolution_headers():
    return {
        "apikey": settings.EVOLUTION_API_KEY,
        "Content-Type": "application/json"
    }

async def send_evolution_text(phone_number: str, message: str):
    """Sends a text message via Evolution API."""
    if not settings.EVOLUTION_API_URL or not settings.EVOLUTION_INSTANCE_NAME:
        logger.error("Evolution API configuration missing")
        return

    url = f"{settings.EVOLUTION_API_URL.rstrip('/')}/message/sendText/{settings.EVOLUTION_INSTANCE_NAME}"
    payload = {
        "number": phone_number,
        "options": {
            "delay": 1200,
            "presence": "composing"
        },
        "textMessage": {
            "text": message
        }
    }
    
    headers = get_evolution_headers()
    
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        response.raise_for_status()

async def download_evolution_media(message_dict: dict) -> bytes:
    """Downloads media from Evolution API using getBase64FromMediaMessage endpoint."""
    if not settings.EVOLUTION_API_URL or not settings.EVOLUTION_INSTANCE_NAME:
        raise ValueError("Evolution API configuration missing")

    url = f"{settings.EVOLUTION_API_URL.rstrip('/')}/chat/getBase64FromMediaMessage/{settings.EVOLUTION_INSTANCE_NAME}"
    payload = {
        "message": message_dict
    }
    
    headers = get_evolution_headers()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        res = await client.post(url, json=payload, headers=headers)
        res.raise_for_status()
        
        data = res.json()
        base64_string = data.get("base64")
        if not base64_string:
            raise ValueError("No base64 data returned from Evolution API")
            
        # The base64 string might include the data URI scheme e.g., 'data:image/jpeg;base64,...'
        if "," in base64_string:
            base64_string = base64_string.split(",")[1]
            
        return base64.b64decode(base64_string)
