import os
import sys
import time
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from app.utils.supabase_client import SupabaseClient

sb = SupabaseClient.get_service_client()
paths = ["snapshots/test.jpg"] * 10
try:
    start = time.time()
    for p in paths:
        res = sb.storage.from_("alert-clips").create_signed_url(p, 3600)
    print("SUCCESS 10 items in", time.time() - start, "seconds")
except Exception as e:
    print("ERROR", str(e))
