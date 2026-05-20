"""
Application Configuration
Load environment variables and provide configuration settings
"""
import os
from typing import List
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "ChildSense AI Backend"
    VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # MongoDB
    MONGODB_URI: str = os.getenv("MONGODB_URI", "")
    MONGODB_DATABASE: str = os.getenv("MONGODB_DATABASE", "childsense_db")
    
    # Supabase
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_SERVICE_KEY: str = os.getenv("SUPABASE_SERVICE_KEY", "")
    
    # Storage Buckets — all profile images share a single bucket (profile-images).
    # Files are named child_<id>_profile.jpg / staff_<id>_profile.jpg etc.
    SUPABASE_BUCKET_PROFILES: str = os.getenv("SUPABASE_BUCKET_PROFILES", "profile-images")
    SUPABASE_BUCKET_ALERTS: str = os.getenv("SUPABASE_BUCKET_ALERTS", "alert-media")
    SUPABASE_BUCKET_FACE_PHOTOS: str = os.getenv("SUPABASE_BUCKET_FACE_PHOTOS", "face-photos")
    
    # JWT Configuration
    SECRET_KEY: str = os.getenv("SECRET_KEY", "default-secret-key-change-this")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    
    # CORS
    CORS_ORIGINS: str = os.getenv(
        "CORS_ORIGINS", 
        "http://localhost:3000,http://localhost:3001,http://localhost:19006"
    )
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as a list"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    # ML Configuration
    ML_SERVICE_URL: str = os.getenv("ML_SERVICE_URL", "http://localhost:8001")
    ML_ALERT_API_KEY: str = os.getenv("ML_ALERT_API_KEY", "childsense-ml-dev-key")
    FACE_MATCH_THRESHOLD: float = float(os.getenv("FACE_MATCH_THRESHOLD", "0.6"))
    
    class Config:
        case_sensitive = True


# Global settings instance
settings = Settings()
