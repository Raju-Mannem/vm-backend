from sqlalchemy import create_engine, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

async_engine = create_async_engine(settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"), echo=False)

# async for FastAPI
AsyncSessionLocal = sessionmaker(
    bind=async_engine, class_=AsyncSession, expire_on_commit=False
)

# sync for Celery Workers
sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
sync_engine = create_engine(sync_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)

async def get_db_session():
    """Dependency for FastAPI"""
    async with AsyncSessionLocal() as session:
        yield session