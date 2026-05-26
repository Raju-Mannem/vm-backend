from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str

    # WhatsApp Cloud API
    WA_VERIFY_TOKEN: str
    WA_APP_SECRET: str
    WA_ACCESS_TOKEN: str
    WA_PHONE_NUMBER_ID: str

    # Cloudinary
    CLOUDINARY_CLOUD_NAME: str
    CLOUDINARY_API_KEY: str
    CLOUDINARY_API_SECRET: str

    # Huggingface
    HF_TOKEN: str

    # Loads from .env file during local development
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()