"""
Database Utilities
MongoDB connection and helper functions
"""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import MongoClient
from typing import Optional
from app.config import settings


class MongoDB:
    """MongoDB connection manager"""
    
    client: Optional[AsyncIOMotorClient] = None
    db: Optional[AsyncIOMotorDatabase] = None
    
    @classmethod
    async def connect_db(cls):
        """Connect to MongoDB"""
        try:
            cls.client = AsyncIOMotorClient(settings.MONGODB_URI)
            cls.db = cls.client[settings.MONGODB_DATABASE]
            
            # Test connection
            await cls.client.admin.command('ping')
            print(f"✅ Connected to MongoDB: {settings.MONGODB_DATABASE}")
            
        except Exception as e:
            print(f"❌ MongoDB connection failed: {e}")
            raise
    
    @classmethod
    async def close_db(cls):
        """Close MongoDB connection"""
        if cls.client:
            cls.client.close()
            print("✅ MongoDB connection closed")
    
    @classmethod
    def get_db(cls):
        """Get database instance (Returns None as MongoDB is removed)"""
        return None

# Dependency for FastAPI routes
async def get_database():
    """FastAPI dependency to get database instance (Returns None)"""
    return None


# Collection names (constants) - ONLY operational data, users are in Supabase
class Collections:
    # User data moved to Supabase:
    # - admins, staff, parents, children are now in Supabase tables
    
    # MongoDB collections (operational data only)
    ROOMS = "rooms"
    CAMERAS = "cameras"
    FACE_EMBEDDINGS = "face_embeddings"
    ALERTS = "alerts"
    ATTENDANCE = "attendance"
    ATTENDANCE_LOGS = "attendance_logs"
    ACTIVITY_LOGS = "activity_logs"
    
    # Legacy collections (for backward compatibility during migration)
    USERS = "users"  # Deprecated - use Supabase
    CHILDREN = "children"  # Deprecated - use Supabase
    ACTIVITY_LOGS = "activity_logs"
