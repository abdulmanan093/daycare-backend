import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from app.utils.supabase_client import SupabaseClient
from app.config import settings
from urllib.parse import unquote

def cleanup_orphaned_profiles():
    supabase = SupabaseClient.get_service_client()
    bucket_name = settings.SUPABASE_BUCKET_PROFILES
    
    print(f"Connecting to Supabase and listing files in bucket: {bucket_name}")
    
    # 1. Fetch all files from the bucket
    try:
        files = supabase.storage.from_(bucket_name).list()
    except Exception as e:
        print(f"Failed to list files: {e}")
        return
        
    bucket_files = {f["name"] for f in files if f["name"] != ".emptyFolderPlaceholder" and f["name"] != ".keep"}
    print(f"Found {len(bucket_files)} files in bucket '{bucket_name}'.")
    
    # 2. Fetch all references from tables
    print("Fetching active profile image references from DB...")
    valid_files = set()
    
    tables_to_check = ["children", "parents", "staff", "admins"]
    
    for table in tables_to_check:
        try:
            res = supabase.table(table).select("profile_image_url").execute()
            for row in res.data or []:
                url = row.get("profile_image_url")
                if url and isinstance(url, str) and bucket_name in url:
                    file_name = url.split(f"/{bucket_name}/")[-1].split("?")[0]
                    file_name = unquote(file_name)
                    valid_files.add(file_name)
        except Exception as e:
            print(f"  Note: Could not check table '{table}': {e}")
            
    print(f"Found {len(valid_files)} valid files referenced across tables.")
    
    # 3. Determine orphaned files
    orphaned_files = list(bucket_files - valid_files)
    
    print(f"Found {len(orphaned_files)} orphaned files to delete.")
    
    if not orphaned_files:
        print("Nothing to clean up!")
        return
        
    # 4. Delete orphaned files in batches
    batch_size = 50
    for i in range(0, len(orphaned_files), batch_size):
        batch = orphaned_files[i:i+batch_size]
        try:
            supabase.storage.from_(bucket_name).remove(batch)
            print(f"Deleted batch {i//batch_size + 1} ({len(batch)} files)...")
            for f in batch:
                print(f"  - Deleted: {f}")
        except Exception as e:
            print(f"Failed to delete batch: {e}")
            
    print("Cleanup complete!")

if __name__ == "__main__":
    cleanup_orphaned_profiles()
