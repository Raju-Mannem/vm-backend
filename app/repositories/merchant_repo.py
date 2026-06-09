from app.models.merchant import Merchant
from pymongo.errors import DuplicateKeyError

class MerchantRepository:
    def __init__(self, session=None):
        pass

    async def upsert_merchant(self, whatsapp_id: str, name: str | None = None) -> Merchant:
        merchant = await Merchant.find_one(Merchant.whatsapp_id == whatsapp_id)
        if merchant:
            if name and merchant.name != name:
                merchant.name = name
                await merchant.save()
            return merchant
            
        try:
            merchant = Merchant(whatsapp_id=whatsapp_id, name=name)
            await merchant.insert()
            return merchant
        except DuplicateKeyError:
            # Handle race condition
            return await Merchant.find_one(Merchant.whatsapp_id == whatsapp_id)