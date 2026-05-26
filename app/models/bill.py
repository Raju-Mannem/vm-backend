from sqlalchemy import Column, String, DateTime, ForeignKey, Enum, Text, func
from .merchant import Base
from .enums import BillStatus

class Bill(Base):
    __tablename__ = "bills"

    id = Column(String, primary_key=True, index=True)
    merchant_id = Column(String, ForeignKey("merchants.id"), nullable=False, index=True)
    whatsapp_message_id = Column(String, unique=True, index=True, nullable=False) # For Idempotency
    
    # Storage
    cloudinary_public_id = Column(String, nullable=False)
    file_url = Column(String, nullable=False) # Internal/Private URL
    
    # State Machine
    status = Column(Enum(BillStatus), default=BillStatus.UPLOADED, nullable=False)
    
    # OCR & Review Data
    raw_ocr_text = Column(Text, nullable=True) # Dumped directly from PaddleOCR
    corrected_data = Column(Text, nullable=True) # JSON string of final reviewed fields (Supplier, Amount, etc.)
    review_notes = Column(String, nullable=True) # Optional notes from the Ops employee
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())