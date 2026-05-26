from sqlalchemy import Column, String, DateTime, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Merchant(Base):
    __tablename__ = "merchants"

    id = Column(String, primary_key=True, index=True)
    whatsapp_id = Column(String, unique=True, index=True, nullable=False)
    name = Column(String, nullable=True) # Populated from WhatsApp profile name
    created_at = Column(DateTime(timezone=True), server_default=func.now()) 