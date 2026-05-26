import cloudinary
import cloudinary.uploader
from app.core.config import settings

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET
)

def upload_bill_image(file_bytes: bytes, filename: str) -> dict:
    """Uploads file securely to Cloudinary."""
    response = cloudinary.uploader.upload(
        file_bytes,
        public_id=f"bills/{filename}",
        type="private",
        resource_type="auto"
    )
    return {
        "public_id": response["public_id"],
        "secure_url": response["secure_url"] 
    }

def get_signed_url(public_id: str) -> str:
    """Generates a temporary URL"""
    return cloudinary.utils.cloudinary_url(
        public_id, 
        type="private", 
        sign_url=True, 
        expires_at=3600 # URL valid for 1 hour
    )[0]