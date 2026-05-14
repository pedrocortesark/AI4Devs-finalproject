#!/usr/bin/env python3
"""
Upload test fixture to Supabase Storage for integration tests.
Usage: docker compose run --rm backend python /app/infra/upload_test_fixture.py
"""
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from supabase_client import get_supabase_client

# Configuration
BUCKET_NAME = "raw-uploads"
SOURCE_FILE = "/app/tests/fixtures/test-model.3dm"
DESTINATION_PATH = "test-fixtures/test-model.3dm"

def main():
    # Initialize client
    supabase = get_supabase_client()
    print(f"🔌 Connected to Supabase")
    
    # Check file exists
    source_path = Path(SOURCE_FILE)
    if not source_path.exists():
        print(f"❌ Error: File not found: {SOURCE_FILE}")
        return 1
    
    file_size_mb = source_path.stat().st_size / (1024 * 1024)
    print(f"📁 File found: {SOURCE_FILE} ({file_size_mb:.2f} MB)")
    
    # Upload file
    print(f"⬆️  Uploading to {BUCKET_NAME}/{DESTINATION_PATH}...")
    
    try:
        with open(source_path, 'rb') as file:
            response = supabase.storage.from_(BUCKET_NAME).upload(
                path=DESTINATION_PATH,
                file=file,
                file_options={"content-type": "application/octet-stream", "upsert": "true"}
            )
        
        print(f"✅ Upload successful!")
        print(f"   Path: {BUCKET_NAME}/{DESTINATION_PATH}")
        print(f"   Size: {file_size_mb:.2f} MB")
        
        # Verify file exists
        print(f"\n🔍 Verifying upload...")
        files = supabase.storage.from_(BUCKET_NAME).list(path="test-fixtures/")
        
        if any(f['name'] == 'test-model.3dm' for f in files):
            print(f"✅ Verification successful - file exists in storage")
        else:
            print(f"⚠️  Warning: File uploaded but not found in listing")
        
        return 0
        
    except Exception as e:
        print(f"❌ Upload failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
