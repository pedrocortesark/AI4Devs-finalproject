#!/usr/bin/env python3
"""
Clean Blocks Without Geometry Script - Non-interactive version
===============================================================

Removes all blocks from the database that don't have complete 3D geometry.
NO CONFIRMATION - USE WITH CAUTION.

Usage:
    docker compose run --rm backend python infra/clean_blocks_no_confirm.py

Author: SF-PM DevTeam
Date: 2026-03-11
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from infra.supabase_client import get_supabase_client


def main():
    print("\n🔍 Connecting to Supabase...")
    supabase = get_supabase_client()
    
    print("📊 Counting blocks...")
    
    # Total non-archived blocks
    total_result = supabase.table("blocks").select("id", count="exact").eq("is_archived", False).execute()
    total_before = total_result.count
    
    # Blocks with complete geometry
    with_geometry_result = (
        supabase.table("blocks")
        .select("id", count="exact")
        .eq("is_archived", False)
        .not_.is_("low_poly_url", "null")
        .not_.is_("bbox", "null")
        .execute()
    )
    with_geometry = with_geometry_result.count
    
    to_delete = total_before - with_geometry
    
    print(f"\n📈 Before:")
    print(f"  • Total blocks: {total_before}")
    print(f"  • With geometry: {with_geometry}")
    print(f"  • Without geometry: {to_delete}")
    
    if to_delete == 0:
        print("\n✅ No blocks to delete.")
        return
    
    print(f"\n🗑️  Deleting {to_delete} blocks...")
    
    # Strategy: Delete in one go using OR condition
    # Delete where low_poly_url IS NULL OR bbox IS NULL
    try:
        # First pass: delete where low_poly_url is NULL
        supabase.table("blocks").delete().eq("is_archived", False).is_("low_poly_url", "null").execute()
        print("  ✓ Deleted blocks without GLB files")
        
        # Second pass: delete where bbox is NULL (catches any remaining)
        supabase.table("blocks").delete().eq("is_archived", False).is_("bbox", "null").execute()
        print("  ✓ Deleted blocks without bounding box")
        
    except Exception as e:
        print(f"  ⚠️  Warning during deletion: {e}")
    
    # Verify
    final_result = supabase.table("blocks").select("id", count="exact").eq("is_archived", False).execute()
    final_total = final_result.count
    
    print(f"\n📊 After:")
    print(f"  • Remaining blocks: {final_total}")
    print(f"  • Deleted: {total_before - final_total}")
    
    if final_total == with_geometry:
        print(f"\n✅ SUCCESS: Database cleaned, {final_total} blocks with geometry remain")
    else:
        print(f"\n⚠️  Expected {with_geometry} but got {final_total} remaining")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
