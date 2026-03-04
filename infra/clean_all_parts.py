#!/usr/bin/env python3
"""
Clean All Parts - Development Script
Deletes all blocks from the database and their associated files from Supabase Storage.

DANGER: This script permanently deletes data. Use only in development.

Usage:
    python infra/clean_all_parts.py

Safety:
    - Requires explicit confirmation
    - Shows preview of parts to be deleted
    - Deletes from both DB and Supabase Storage
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import psycopg2
from psycopg2.extras import RealDictCursor
from infra.supabase_client import get_supabase_client

# Get database URL from environment
DATABASE_URL = os.getenv('SUPABASE_DATABASE_URL')
if not DATABASE_URL:
    raise ValueError("SUPABASE_DATABASE_URL environment variable not set")

def get_db_connection():
    """Create PostgreSQL connection."""
    return psycopg2.connect(DATABASE_URL)

def preview_parts():
    """Show preview of parts that will be deleted."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        cursor.execute("""
            SELECT id, iso_code, status, tipologia, created_at
            FROM blocks
            ORDER BY created_at DESC
        """)
        parts = cursor.fetchall()
        
        if not parts:
            print("✓ No parts found in database.")
            return []
        
        print(f"\n{'='*80}")
        print(f"PARTS TO BE DELETED ({len(parts)} total)")
        print(f"{'='*80}")
        
        for part in parts:
            print(f"  • {part['iso_code']:<30} | {part['status']:<15} | {part['tipologia']:<15}")
            print(f"    ID: {part['id']}")
            print(f"    Created: {part['created_at']}")
            print()
        
        return parts
        
    finally:
        cursor.close()
        conn.close()

def delete_from_storage(file_urls):
    """Delete files from Supabase Storage."""
    if not file_urls:
        return
    
    supabase = get_supabase_client()
    deleted = 0
    errors = 0
    
    print("\n🗑️  Deleting files from Supabase Storage...")
    
    for url in file_urls:
        if not url:
            continue
            
        try:
            # Extract path from URL
            # Format: https://xxx.supabase.co/storage/v1/object/public/processed-geometry/xxx.glb
            if '/processed-geometry/' in url:
                path = url.split('/processed-geometry/')[-1]
                
                response = supabase.storage.from_('processed-geometry').remove([path])
                deleted += 1
                print(f"  ✓ Deleted: {path}")
            
        except Exception as e:
            errors += 1
            print(f"  ✗ Error deleting {url}: {e}")
    
    print(f"\n  Storage cleanup: {deleted} deleted, {errors} errors")

def delete_all_parts():
    """Delete all parts from database and storage."""
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)
    
    try:
        # Get all GLB URLs before deleting
        cursor.execute("""
            SELECT low_poly_url, url_original
            FROM blocks
        """)
        rows = cursor.fetchall()
        
        file_urls = []
        for row in rows:
            file_urls.extend([row.get('low_poly_url'), row.get('url_original')])
        
        file_urls = [url for url in file_urls if url]  # Filter None values
        
        # Delete from storage first
        delete_from_storage(file_urls)
        
        # Delete from database
        print("\n🗑️  Deleting from database...")
        cursor.execute("DELETE FROM blocks")
        deleted_count = cursor.rowcount
        conn.commit()
        
        print(f"  ✓ Deleted {deleted_count} parts from database")
        print(f"\n{'='*80}")
        print("✅ CLEANUP COMPLETE")
        print(f"{'='*80}")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error during deletion: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

def main():
    print(f"\n{'='*80}")
    print("CLEAN ALL PARTS - Development Script")
    print(f"{'='*80}")
    print("\n⚠️  WARNING: This will permanently delete ALL parts from:")
    print("  • PostgreSQL database (blocks table)")
    print("  • Supabase Storage (processed-geometry bucket)")
    print()
    
    # Preview parts
    parts = preview_parts()
    
    if not parts:
        print("Nothing to delete. Exiting.")
        return
    
    # Confirmation
    print(f"\n{'='*80}")
    response = input(f"Delete {len(parts)} parts? Type 'yes' to confirm: ").strip().lower()
    
    if response != 'yes':
        print("❌ Cancelled. No changes made.")
        return
    
    # Execute deletion
    delete_all_parts()
    
    print("\n✓ Database is now clean. You can upload new .3dm files.")
    print("  Next steps:")
    print("    1. Go to http://localhost:5173/")
    print("    2. Upload your .3dm file")
    print("    3. Monitor agent-worker logs: docker compose logs -f agent-worker")

if __name__ == '__main__':
    main()
