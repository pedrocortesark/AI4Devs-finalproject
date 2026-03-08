#!/usr/bin/env python3
"""
Database Infrastructure Initialization Script
Creates Supabase storage buckets using the Storage API.
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Import centralized constants
# In Docker: constants.py is at /app/constants.py (backend root)
sys.path.insert(0, str(Path(__file__).parent.parent))
from constants import STORAGE_BUCKET_RAW_UPLOADS, STORAGE_BUCKET_PROCESSED

# Load environment variables from .env
load_dotenv()

def main():
    # Get Supabase credentials from environment
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not all([supabase_url, supabase_key]):
        print("❌ ERROR: Missing Supabase credentials in environment variables")
        print("Required variables: SUPABASE_URL, SUPABASE_KEY")
        print(f"Current SUPABASE_URL: {supabase_url or '[MISSING]'}")
        print(f"Current SUPABASE_KEY: {'[SET]' if supabase_key else '[MISSING]'}")
        return 1

    # Import supabase client
    try:
        from supabase import create_client, Client
    except ImportError:
        print("❌ ERROR: supabase library not installed")
        print("Run: pip install supabase")
        print("Or rebuild Docker image: docker-compose build backend")
        return 1

    # Create Supabase client
    print(f"🔌 Connecting to Supabase at {supabase_url}...")
    try:
        supabase: Client = create_client(supabase_url, supabase_key)
    except Exception as e:
        print(f"❌ ERROR: Failed to create Supabase client: {e}")
        return 1

    # Create storage buckets
    buckets_to_create = [
        (STORAGE_BUCKET_RAW_UPLOADS, False),    # private: presigned URLs
        (STORAGE_BUCKET_PROCESSED, True),        # public: GLB files served directly
    ]

    for bucket_name, is_public in buckets_to_create:
        print(f"📦 Creating storage bucket '{bucket_name}' (public={is_public})...")
        try:
            supabase.storage.create_bucket(
                bucket_name,
                options={"public": is_public}
            )
            print(f"✅ SUCCESS: Bucket '{bucket_name}' created!")
        except Exception as e:
            error_msg = str(e)
            if "already exists" in error_msg.lower() or "duplicate" in error_msg.lower():
                print(f"ℹ️  Bucket '{bucket_name}' already exists (skipping)")
            else:
                print(f"❌ ERROR: Failed to create bucket '{bucket_name}': {e}")
                return 1

    # Verify both buckets exist
    print("\n🔍 Verifying bucket existence...")
    try:
        buckets = supabase.storage.list_buckets()
        bucket_names = [b.name for b in buckets]
        required = [STORAGE_BUCKET_RAW_UPLOADS, STORAGE_BUCKET_PROCESSED]
        missing = [b for b in required if b not in bucket_names]

        if missing:
            print(f"⚠️  WARNING: Missing buckets: {missing}")
            print(f"   Available buckets: {bucket_names}")
            return 1

        print(f"✅ VERIFIED: All buckets exist: {bucket_names}")
    except Exception as e:
        print(f"⚠️  Could not verify buckets: {e}")

    print("\n✅ Infrastructure setup completed!")
    print("\n🧪 Next step: Run 'make test-storage' to verify")

    return 0

if __name__ == "__main__":
    sys.exit(main())
