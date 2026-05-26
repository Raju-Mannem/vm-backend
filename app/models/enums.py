import enum

class BillStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    QUEUED_FOR_OCR = "QUEUED_FOR_OCR"
    OCR_FAILED = "OCR_FAILED"         # Failed after 3 retries
    REVIEW_PENDING = "REVIEW_PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"