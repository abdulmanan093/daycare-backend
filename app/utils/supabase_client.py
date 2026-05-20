"""
Supabase Client
Handles Supabase authentication and storage operations
"""
from supabase import create_client, Client
from app.config import settings
from typing import Optional


class SupabaseClient:
    """Supabase connection manager"""
    
    _client: Optional[Client] = None
    
    @classmethod
    def get_client(cls) -> Client:
        """Get or create Supabase client instance"""
        if cls._client is None:
            cls._client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_KEY
            )
            print(" [OK] Supabase client initialized")
        return cls._client
    
    @classmethod
    def get_service_client(cls) -> Client:
        """Get Supabase client with service role key (for admin operations)"""
        return create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY
        )


# Global instance
supabase_client = SupabaseClient.get_client()
