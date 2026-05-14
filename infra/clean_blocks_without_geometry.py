#!/usr/bin/env python3
"""
Clean Blocks Without Geometry Script
=====================================

Removes all blocks from the database that don't have complete 3D geometry:
- Missing low_poly_url (no GLB file)
- Missing bbox (no bounding box)

This keeps only render-ready elements (visible in /api/elements).

Usage:
    docker compose run --rm backend python infra/clean_blocks_without_geometry.py

Author: SF-PM DevTeam
Date: 2026-03-11
Context: US-015 Cleanup - Remove obsolete blocks without 3D models
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.supabase_client import get_supabase_client


def confirm_deletion(count: int) -> bool:
    """Ask user for confirmation before proceeding."""
    print("\n" + "="*70)
    print("⚠️  DELETE BLOCKS WITHOUT GEOMETRY - CONFIRMATION REQUIRED")
    print("="*70)
    print(f"\nThis script will DELETE {count} blocks that are missing:")
    print("  • low_poly_url (no GLB file)")
    print("  • bbox (no bounding box)")
    print("\n✅ Blocks with complete geometry will be PRESERVED")
    print("\n❌ This operation is IRREVERSIBLE")
    print("\n" + "="*70)
    
    response = input(f"\nType 'DELETE {count}' to proceed (anything else to cancel): ")
    return response.strip() == f"DELETE {count}"


def get_block_counts(supabase):
    """Get counts of blocks with and without geometry."""
    # Total non-archived blocks
    total_result = supabase.table("blocks").select("id", count="exact").eq("is_archived", False).execute()
    total_count = total_result.count
    
    # Blocks with complete geometry (render-ready)
    with_geometry_result = (
        supabase.table("blocks")
        .select("id", count="exact")
        .eq("is_archived", False)
        .not_.is_("low_poly_url", "null")
        .not_.is_("bbox", "null")
        .execute()
    )
    with_geometry_count = with_geometry_result.count
    
    # Blocks without complete geometry (to be deleted)
    without_geometry_count = total_count - with_geometry_count
    
    return {
        "total": total_count,
        "with_geometry": with_geometry_count,
        "without_geometry": without_geometry_count
    }


def delete_blocks_without_geometry(supabase):
    """Delete all blocks that don't have low_poly_url OR bbox."""
    # Delete blocks where low_poly_url is NULL
    result1 = (
        supabase.table("blocks")
        .delete()
        .eq("is_archived", False)
        .is_("low_poly_url", "null")
        .execute()
    )
    deleted_no_url = len(result1.data) if result1.data else 0
    
    # Delete blocks where bbox is NULL (and low_poly_url exists)
    result2 = (
        supabase.table("blocks")
        .delete()
        .eq("is_archived", False)
        .is_("bbox", "null")
        .execute()
    )
    deleted_no_bbox = len(result2.data) if result2.data else 0
    
    return deleted_no_url + deleted_no_bbox


def main():
    """Main execution flow."""
    print("\n🔍 Connecting to Supabase...")
    supabase = get_supabase_client()
    
    print("📊 Analyzing database...")
    counts = get_block_counts(supabase)
    
    print(f"\n📈 Current State:")
    print(f"  • Total blocks: {counts['total']}")
    print(f"  • With complete geometry (GLB + bbox): {counts['with_geometry']}")
    print(f"  • Without complete geometry: {counts['without_geometry']}")
    
    if counts['without_geometry'] == 0:
        print("\n✅ No blocks to delete. All blocks have complete geometry.")
        return
    
    # Confirm deletion
    if not confirm_deletion(counts['without_geometry']):
        print("\n❌ Operation cancelled by user.")
        return
    
    print(f"\n🗑️  Deleting {counts['without_geometry']} blocks without geometry...")
    deleted_count = delete_blocks_without_geometry(supabase)
    
    print(f"\n✅ Deleted {deleted_count} blocks")
    
    # Verify final state
    print("\n🔍 Verifying final state...")
    final_counts = get_block_counts(supabase)
    print(f"\n📈 Final State:")
    print(f"  • Total blocks: {final_counts['total']}")
    print(f"  • With complete geometry: {final_counts['with_geometry']}")
    print(f"  • Without complete geometry: {final_counts['without_geometry']}")
    
    if final_counts['without_geometry'] == 0:
        print("\n✅ SUCCESS: All remaining blocks have complete geometry")
    else:
        print(f"\n⚠️  WARNING: {final_counts['without_geometry']} blocks still without geometry")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Operation cancelled by user (Ctrl+C)")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
