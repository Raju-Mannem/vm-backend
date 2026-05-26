import redis.asyncio as redis
from app.core.config import settings

redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

async def check_and_lock_message(message_id: str) -> bool:
    """
    Returns True if this is a new message.
    Returns False if the message_id already exists (duplicate).
    TTL is set to 24 hours (86400 seconds).
    """
    # nx=True ensures the key is only set if it doesn't already exist.
    is_new = await redis_client.set(
        f"webhook:msg:{message_id}", 
        "processing", 
        ex=86400, 
        nx=True 
    )
    return bool(is_new)