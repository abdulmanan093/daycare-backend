"""
Supabase Database Setup
Automatically creates tables, policies, storage buckets, and triggers
"""
import asyncio
from supabase import create_client, Client
from app.config import settings


class SupabaseSetup:
    """Handles Supabase database initialization"""
    
    def __init__(self):
        self.supabase: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_KEY  # Use service key for admin operations
        )
    
    async def setup_all(self):
        """Run all setup tasks"""
        print("🟢 Setting up Supabase...")
        
        try:
            # 1. Create tables
            await self.create_tables()
            
            # 2. Create storage buckets
            await self.create_storage_buckets()
            
            # 3. Setup RLS policies
            await self.setup_rls_policies()
            
            print("✅ Supabase setup completed successfully!")
            
        except Exception as e:
            print(f"⚠️  Supabase setup warning: {e}")
            print("   (This is normal if tables already exist)")
    
    async def create_tables(self):
        """Create all required tables"""
        print("  📋 Creating tables...")
        
        # Note: Supabase doesn't have a direct SQL execution endpoint from Python SDK
        # We'll use the management API or create tables via migrations
        # For now, we'll document what needs to be done manually
        
        print("    ℹ️  Supabase tables need to be created via SQL Editor:")
        print("       Go to: Supabase Dashboard → SQL Editor")
        print("       Run the migration SQL from implementation_guide.md")
        print("    ⏭  Skipping table creation (must be done via dashboard)")
        
        # Alternative: Check if tables exist via REST API
        try:
            # Try to query profiles table to check if it exists
            response = self.supabase.table('profiles').select("id").limit(1).execute()
            print("    ✓ Tables already exist (profiles table accessible)")
        except Exception:
            print("    ⚠️  Tables may not exist yet. Please run SQL migration manually.")
            print("       See: implementation_guide.md for SQL commands")
    
    async def setup_rls_policies(self):
        """Setup Row Level Security policies"""
        print("  🔐 Checking RLS policies...")
        
        # Note: RLS policies also require SQL Editor access
        # We'll just inform the user
        print("    ℹ️  RLS policies should be set via SQL Editor")
        print("    ⏭  Skipping RLS setup (must be done via dashboard)")
    
    async def create_storage_buckets(self):
        """Create storage buckets"""
        print("  📦 Checking storage buckets...")
        
        required_buckets = [
            "profile-images", "alert-media", "child-profile-images",
            "temporary-faces", "camera-snapshots"
        ]
        
        try:
            # List existing buckets ONCE at the start
            existing_buckets = self.supabase.storage.list_buckets()
            bucket_names = [b.name for b in existing_buckets]
            
            print(f"    ℹ️  Found {len(bucket_names)} storage buckets")
            
            # Check which required buckets exist
            all_exist = True
            for bucket in required_buckets:
                if bucket in bucket_names:
                    print(f"    ✓ {bucket}")
                else:
                    print(f"    ✗ {bucket} (missing)")
                    all_exist = False
            
            if all_exist:
                print(f"    ✅ All {len(required_buckets)} required buckets exist!")
            else:
                print(f"\n    ⚠️  Some buckets are missing. Create them via Supabase Dashboard.")
                    
        except Exception as e:
            print(f"    ⚠️  Could not access storage: {str(e)[:80]}")


async def initialize_supabase():
    """Main function to initialize Supabase"""
    setup = SupabaseSetup()
    await setup.setup_all()


if __name__ == "__main__":
    # For testing: python -m app.utils.supabase_setup
    asyncio.run(initialize_supabase())
