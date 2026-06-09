from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.core.config import settings
from app.models.merchant import Merchant
from app.models.bill import Bill
from app.models.chat import ChatMessage

async def init_db():
    client = AsyncIOMotorClient(settings.DATABASE_URL)
    # The default DB name will be extracted from the connection string or defaulted to 'vm_database'
    database = client.get_default_database("vm_database")
    
    await init_beanie(
        database=database,
        document_models=[
            Merchant,
            Bill,
            ChatMessage
        ]
    )
