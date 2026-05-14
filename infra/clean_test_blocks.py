#!/usr/bin/env python3
"""
Clean test blocks and their storage files.

This script deletes blocks from the database and removes their associated
files from Supabase Storage (both raw-uploads and processed-geometry buckets).

Usage:
    # List blocks that will be deleted (dry-run)
    python infra/clean_test_blocks.py --dry-run
    
    # Delete specific ISO codes
    python infra/clean_test_blocks.py --iso GLPER.B-PAE0720.0701 GLPER.B-PAE0720.0702
    
    # Delete all blocks matching test-model.3dm
    python infra/clean_test_blocks.py --all-test-blocks
    
    # Force deletion without confirmation
    python infra/clean_test_blocks.py --all-test-blocks --yes
"""

import sys
import argparse
from pathlib import Path
from typing import List

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from infra.supabase_client import get_supabase_client
    import structlog
except ImportError as e:
    print(f"❌ Error importing dependencies: {e}")
    print("Run: docker compose run --rm backend python /app/infra/clean_test_blocks.py")
    sys.exit(1)

logger = structlog.get_logger()


def find_test_blocks(supabase) -> List[dict]:
    """Find all blocks using test-model.3dm or with empty metadata.
    
    Returns:
        List of block records
    """
    response = supabase.table('blocks').select(
        'id, iso_code, url_original, high_poly_url, mid_poly_url, low_poly_url, rhino_metadata'
    ).not_.is_('bbox', 'null').execute()
    
    test_blocks = []
    for block in response.data:
        # Check if using test file or has empty metadata
        url_original = block.get('url_original', '')
        metadata = block.get('rhino_metadata')
        
        is_test_file = 'test-model.3dm' in url_original
        is_empty_metadata = metadata is None or (isinstance(metadata, dict) and len(metadata) == 0)
        
        if is_test_file or is_empty_metadata:
            test_blocks.append(block)
    
    return test_blocks


def delete_storage_files(supabase, block: dict) -> dict:
    """Delete all storage files associated with a block.
    
    Args:
        supabase: Supabase client
        block: Block record
    
    Returns:
        Dictionary with deletion results
    """
    results = {
        'raw_uploads': None,
        'processed_files': []
    }
    
    block_id = block['id']
    
    # 1. Delete raw upload (if exists)
    url_original = block.get('url_original')
    if url_original:
        # url_original format: "uploads/block-id/filename.3dm"
        try:
            path = url_original.replace('uploads/', '')
            supabase.storage.from_('raw-uploads').remove([path])
            results['raw_uploads'] = 'deleted'
            logger.info("deleted_raw_upload", block_id=block_id, path=path)
        except Exception as e:
            results['raw_uploads'] = f'error: {str(e)}'
            logger.warning("raw_upload_delete_failed", block_id=block_id, error=str(e))
    
    # 2. Delete processed files (high/mid/low poly)
    for poly_type in ['high_poly_url', 'mid_poly_url', 'low_poly_url']:
        url = block.get(poly_type)
        if url:
            try:
                # URL format: "https://xxx.supabase.co/storage/v1/object/public/processed-geometry/glb/block-id/file.glb"
                # Extract path after processed-geometry/
                parts = url.split('/processed-geometry/')
                if len(parts) == 2:
                    path = parts[1].rstrip('?')  # Remove trailing '?' if present
                    supabase.storage.from_('processed-geometry').remove([path])
                    results['processed_files'].append({
                        'type': poly_type,
                        'path': path,
                        'status': 'deleted'
                    })
                    logger.info("deleted_processed_file", block_id=block_id, type=poly_type, path=path)
            except Exception as e:
                results['processed_files'].append({
                    'type': poly_type,
                    'path': url,
                    'status': f'error: {str(e)}'
                })
                logger.warning("processed_file_delete_failed", block_id=block_id, type=poly_type, error=str(e))
    
    return results


def delete_block(supabase, block: dict, delete_files: bool = True) -> bool:
    """Delete a block and optionally its storage files.
    
    Args:
        supabase: Supabase client
        block: Block record
        delete_files: If True, delete storage files first
    
    Returns:
        True if successful
    """
    block_id = block['id']
    iso_code = block['iso_code']
    
    logger.info("deleting_block", block_id=block_id, iso_code=iso_code)
    
    # Delete storage files first
    if delete_files:
        storage_results = delete_storage_files(supabase, block)
        logger.info("storage_cleanup_complete", block_id=block_id, results=storage_results)
    
    # Delete from database
    try:
        supabase.table('blocks').delete().eq('id', block_id).execute()
        logger.info("block_deleted", block_id=block_id, iso_code=iso_code)
        return True
    except Exception as e:
        logger.error("block_delete_failed", block_id=block_id, iso_code=iso_code, error=str(e))
        return False


def main():
    parser = argparse.ArgumentParser(description='Clean test blocks and storage')
    parser.add_argument('--iso', nargs='+', help='Specific ISO codes to delete')
    parser.add_argument('--all-test-blocks', action='store_true', help='Delete all blocks using test-model.3dm')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be deleted without deleting')
    parser.add_argument('--yes', action='store_true', help='Skip confirmation prompt')
    parser.add_argument('--keep-files', action='store_true', help='Delete only database records (keep storage files)')
    args = parser.parse_args()
    
    supabase = get_supabase_client()
    
    # Find blocks to delete
    if args.iso:
        # Delete specific ISO codes
        response = supabase.table('blocks').select(
            'id, iso_code, url_original, high_poly_url, mid_poly_url, low_poly_url, rhino_metadata'
        ).in_('iso_code', args.iso).execute()
        blocks_to_delete = response.data
    elif args.all_test_blocks:
        # Delete all test blocks
        blocks_to_delete = find_test_blocks(supabase)
    else:
        # Default: list test blocks (dry-run)
        blocks_to_delete = find_test_blocks(supabase)
        args.dry_run = True
    
    if not blocks_to_delete:
        print("\n✅ No blocks found to delete")
        return
    
    # Display blocks
    print("\n" + "="*80)
    print(f"{'🔍 BLOCKS TO DELETE (DRY RUN)' if args.dry_run else '⚠️  BLOCKS TO DELETE'}")
    print("="*80 + "\n")
    
    for i, block in enumerate(blocks_to_delete, 1):
        print(f"{i}. {block['iso_code']}")
        print(f"   ID: {block['id']}")
        print(f"   Original: {block.get('url_original', 'N/A')}")
        
        metadata = block.get('rhino_metadata')
        metadata_status = 'empty' if (metadata is None or len(metadata) == 0) else f'{len(metadata)} keys'
        print(f"   Metadata: {metadata_status}")
        
        has_files = any([
            block.get('url_original'),
            block.get('high_poly_url'),
            block.get('mid_poly_url'),
            block.get('low_poly_url')
        ])
        print(f"   Storage files: {'yes' if has_files else 'no'}")
        print()
    
    print("-" * 80)
    print(f"Total: {len(blocks_to_delete)} blocks")
    print("="*80 + "\n")
    
    if args.dry_run:
        print("💡 This was a dry-run. No changes made.")
        print("   Remove --dry-run to actually delete these blocks.")
        return
    
    # Confirmation
    if not args.yes:
        print("⚠️  WARNING: This will permanently delete:")
        print(f"   • {len(blocks_to_delete)} database records")
        if not args.keep_files:
            print("   • All associated storage files (3DM, GLB, OBJ)")
        print()
        response = input("Type 'DELETE' to confirm: ").strip()
        if response != 'DELETE':
            print("\n❌ Cancelled by user")
            return
    
    # Delete blocks
    print("\n" + "="*80)
    print("🗑️  DELETING BLOCKS")
    print("="*80 + "\n")
    
    success_count = 0
    error_count = 0
    
    for block in blocks_to_delete:
        iso_code = block['iso_code']
        print(f"Processing: {iso_code}...")
        
        success = delete_block(supabase, block, delete_files=not args.keep_files)
        
        if success:
            success_count += 1
            print(f"  ✅ Deleted\n")
        else:
            error_count += 1
            print(f"  ❌ Failed\n")
    
    # Summary
    print("="*80)
    print("📊 SUMMARY")
    print("="*80)
    print(f"  Total: {len(blocks_to_delete)}")
    print(f"  ✅ Success: {success_count}")
    print(f"  ❌ Errors: {error_count}")
    print()
    
    if success_count > 0:
        print("✅ Blocks deleted successfully")
        print("   You can now upload new files through the UI")


if __name__ == '__main__':
    main()
