import cloudinary
import cloudinary.uploader
from app.core.config import settings

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET
)

def upload_bill_image(file_bytes: bytes, filename: str) -> dict:
    """Uploads file securely to Cloudinary and extracts OCR text."""
    response = cloudinary.uploader.upload(
        file_bytes,
        public_id=f"bills/{filename}",
        type="private",
        resource_type="auto",
        ocr="adv_ocr"
    )
    
    # Extract OCR data
    raw_text = ""
    info = response.get("info", {})
    ocr_data = info.get("ocr", {}).get("adv_ocr", {}).get("data", [])
    
    if ocr_data and len(ocr_data) > 0:
        annotations = ocr_data[0].get("textAnnotations", [])
        if annotations and len(annotations) > 0:
            # The first annotation contains the entire block of concatenated text
            raw_text = annotations[0].get("description", "")
            
    return {
        "public_id": response["public_id"],
        "secure_url": response["secure_url"],
        "raw_text": raw_text
    }

def get_signed_url(public_id: str) -> str:
    """Generates a temporary URL"""
    return cloudinary.utils.cloudinary_url(
        public_id, 
        type="private", 
        sign_url=True, 
        expires_at=3600 # URL valid for 1 hour
    )[0]