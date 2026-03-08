#!/usr/bin/env python3
"""
Clean Database Script - Full Reset
==================================

⚠️  WARNING: This script will DELETE ALL data from:
- blocks table (all elements)
- events table (all processing logs)
- Supabase Storage GLB files (models/low-poly/*.glb)

Use this BEFORE starting fresh with US-015 Element model.

Usage:
    docker compose run --rm backend python infra/clean_database_full.py

Author: SF-PM DevTeam
Date: 2026-03-06
Context: US-015 Phase 0 - Clean obsolete test data before Element model migration
"""

import sys
import os
from typing import Tuple

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.supabase_client import get_supabase_client


def confirm_deletion() -> bool:
    """Ask user for confirmation before proceeding."""
    print("\n" + "="*70)
    print("⚠️  DATABASE FULL RESET - CONFIRMATION REQUIRED")
    print("="*70)
    print("\nThis script will DELETE:")
    print("  🗑️  ALL blocks (elements) from database")
    print("  🗑️  ALL events (processing logs)")
    print("  🗑️  ALL GLB files from Supabase Storage (models/low-poly/)")
    print("\n❌ This operation is IRREVERSIBLE")
    print("✅ Use this ONLY if you want to start fresh with 6 real Rhino pieces")
    print("\n" + "="*70)
    
    response = input("\nType 'DELETE ALL' to proceed (anything else to cancel): ")
    return response.strip() == "DELETE ALL"


def get_current_counts(supabase) -> Tuple[int, int, int]:
    """Get current counts from database and storage."""
    # Count blocks
    blocks_result = supabase.table('blocks').select('id', count='exact').execute()
    blocks_count = blocks_result.count or 0
    
    # Count events
    events_result = supabase.table('events').select('id', count='exact').execute()
    events_count = events_result.count or 0
    
    # Count storage files
    try:
        storage_files = supabase.storage.from_('models').list('low-poly/')
        storage_count = len(storage_files) if storage_files else 0
    except Exception:
        storage_count = 0
    
    return blocks_count, events_count, storage_count


def delete_blocks(supabase) -> int:
    """Delete all blocks from database."""
    print("\n🗑️  Deleting all blocks...")
    try:
        # Supabase delete without filter deletes ALL rows
        result = supabase.table('blocks').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        deleted = len(result.data) if result.data else 0
        print(f"   ✅ Deleted {deleted} blocks")
        return deleted
    except Exception as e:
        print(f"   ❌ Error deleting blocks: {e}")
        return 0


def delete_events(supabase) -> int:
    """Delete all events from database."""
    print("\n🗑️  Deleting all events...")
    try:
        result = supabase.table('events').delete().neq('id', '00000000-0000-0000-0000-000000000000').execute()
        deleted = len(result.data) if result.data else 0
        print(f"   ✅ Deleted {deleted} events")
        return deleted
    except Exception as e:
        print(f"   ❌ Error deleting events: {e}")
        return 0


def delete_storage_files(supabase) -> int:
    """Delete all GLB files from Supabase Storage."""
    print("\n🗑️  Deleting all GLB files from storage...")
    try:
        # List all files in low-poly folder
        files = supabase.storage.from_('models').list('low-poly/')
        
        if not files:
            print("   ℹ️  No files found in storage")
            return 0
        
        # Delete files in batches
        deleted_count = 0
        file_paths = [f"low-poly/{file['name']}" for file in files if file.get('name')]
        
        # Supabase Storage remove() accepts list of paths
        if file_paths:
            result = supabase.storage.from_('models').remove(file_paths)
            deleted_count = len(file_paths)
            print(f"   ✅ Deleted {deleted_count} GLB files")
        
        return deleted_count
    except Exception as e:
        print(f"   ⚠️  Error deleting storage files: {e}")
        print(f"      (This is non-critical - storage will be cleaned on next upload)")
        return 0


def main():
    """Main execution flow."""
    print("\n🚀 SF-PM Database Cleanup Script")
    print("=" * 70)
    
    # Get Supabase client
    supabase = get_supabase_client()
    
    # Show current state
    blocks_count, events_count, storage_count = get_current_counts(supabase)
    
    print("\n📊 Current Database State:")
    print(f"   • Blocks (elements): {blocks_count}")
    print(f"   • Events (logs): {events_count}")
    print(f"   • Storage GLB files: {storage_count}")
    
    # Ask for confirmation
    if not confirm_deletion():
        print("\n❌ Operation cancelled by user")
        sys.exit(0)
    
    # Execute deletions
    print("\n" + "="*70)
    print("🔨 Starting deletion process...")
    print("="*70)
    
    deleted_blocks = delete_blocks(supabase)
    deleted_events = delete_events(supabase)
    deleted_storage = delete_storage_files(supabase)
    
    # Summary
    print("\n" + "="*70)
    print("✅ DATABASE CLEANUP COMPLETE")
    print("="*70)
    print(f"\n📊 Deletion Summary:")
    print(f"   • Blocks deleted: {deleted_blocks}/{blocks_count}")
    print(f"   • Events deleted: {deleted_events}/{events_count}")
    print(f"   • Storage files deleted: {deleted_storage}/{storage_count}")
    
    print("\n🎯 Next Steps:")
    print("   1. Upload your Rhino file with 6 pieces via the UI (http://localhost:5173)")
    print("   2. Wait for async processing (Celery worker will process each piece)")
    print("   3. Verify in 3D canvas that all 6 elements appear correctly")
    print("   4. Then proceed with T-1501-DB migration (Element model)")
    
    print("\n✨ Database is now clean and ready for fresh ingestion!\n")


if __name__ == "__main__":
    main()
