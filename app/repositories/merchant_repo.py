import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from app.models.merchant import Merchant

class MerchantRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_merchant(self, whatsapp_id: str, name: str | None = None) -> Merchant:
        """
        Atomically creates a new merchant or updates their name if they exist.
        Prevents race conditions during high-volume webhook bursts.
        """
        stmt = insert(Merchant).values(
            id=str(uuid.uuid4()),
            whatsapp_id=whatsapp_id,
            name=name
        ).on_conflict_do_update(
            index_elements=['whatsapp_id'],
            set_={"name": name}
        ).returning(Merchant)

        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.scalar_one()