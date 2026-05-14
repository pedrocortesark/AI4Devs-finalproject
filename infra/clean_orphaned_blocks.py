#!/usr/bin/env python3
"""
Limpia blocks sin archivo original (.3dm) - no pueden ser reprocesados

USO:
    python infra/clean_orphaned_blocks.py --dry-run    # Ver qué se borraría
    python infra/clean_orphaned_blocks.py --yes        # Ejecutar limpieza
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("❌ ERROR: psycopg2-binary not installed")
    sys.exit(1)


def load_config():
    """Load database URL from environment"""
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    load_dotenv(env_file)
    
    database_url = os.getenv("SUPABASE_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ ERROR: SUPABASE_DATABASE_URL not set")
        sys.exit(1)
    
    return database_url


def clean_orphaned_blocks(database_url: str, dry_run: bool = True):
    """Delete blocks without url_original (cannot be reprocessed)"""
    
    conn = psycopg2.connect(database_url)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Count blocks to delete
    cur.execute("""
        SELECT COUNT(*) as count
        FROM blocks
        WHERE url_original IS NULL
        AND NOT is_archived;
    """)
    count = cur.fetchone()['count']
    
    if count == 0:
        print("✅ No orphaned blocks found. Database is clean.")
        cur.close()
        conn.close()
        return
    
    # Show sample blocks
    cur.execute("""
        SELECT iso_code, status, created_at
        FROM blocks
        WHERE url_original IS NULL
        AND NOT is_archived
        ORDER BY created_at DESC
        LIMIT 10;
    """)
    samples = cur.fetchall()
    
    print(f"🗑️  Found {count} blocks without original .3dm file:")
    print()
    for block in samples:
        print(f"   {block['iso_code']}: status={block['status']}, created={block['created_at']}")
    if count > 10:
        print(f"   ... and {count - 10} more")
    print()
    
    if dry_run:
        print("🔍 DRY RUN MODE - No changes made")
        print("   To execute cleanup, run with --yes flag")
    else:
        print("⚠️  DELETING blocks without original files...")
        cur.execute("""
            DELETE FROM blocks
            WHERE url_original IS NULL
            AND NOT is_archived
            RETURNING iso_code;
        """)
        deleted = cur.fetchall()
        conn.commit()
        
        print(f"✅ Deleted {len(deleted)} blocks:")
        for block in deleted[:10]:
            print(f"   - {block['iso_code']}")
        if len(deleted) > 10:
            print(f"   ... and {len(deleted) - 10} more")
    
    cur.close()
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Clean blocks without original .3dm files"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Show what would be deleted without making changes (default)"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Actually execute the cleanup (overrides --dry-run)"
    )
    args = parser.parse_args()
    
    database_url = load_config()
    
    # --yes overrides --dry-run
    dry_run = not args.yes
    
    clean_orphaned_blocks(database_url, dry_run=dry_run)
