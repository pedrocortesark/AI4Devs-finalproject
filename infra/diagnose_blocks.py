#!/usr/bin/env python3
"""
Script de Diagnóstico de Blocks - Identifica bloques sin geometría LOD

USO:
    python infra/diagnose_blocks.py

Muestra:
- Total de blocks en base de datos
- Blocks con geometría LOD completa (ready para dashboard)
- Blocks sin geometría LOD (necesitan reprocesamiento)
- Blocks sin archivo original (creados manualmente, no pueden reprocesarse)
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
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


def diagnose_blocks(database_url: str):
    """Analyze blocks and show their LOD processing status"""
    
    conn = psycopg2.connect(database_url)
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    # Get all blocks
    cur.execute("""
        SELECT 
            COUNT(*) as total,
            COUNT(url_original) as with_original,
            COUNT(low_poly_url) as with_low_poly,
            COUNT(mid_poly_url) as with_mid_poly,
            COUNT(high_poly_url) as with_high_poly
        FROM blocks
        WHERE NOT is_archived;
    """)
    stats = cur.fetchone()
    
    print("=" * 70)
    print("📊 BLOCKS STATUS SUMMARY")
    print("=" * 70)
    print(f"Total blocks:               {stats['total']}")
    print(f"With original .3dm file:    {stats['with_original']}")
    print(f"With low_poly_url:          {stats['with_low_poly']}")
    print(f"With mid_poly_url:          {stats['with_mid_poly']}")
    print(f"With high_poly_url:         {stats['with_high_poly']}")
    print()
    
    # Get blocks ready for dashboard (have low_poly_url)
    cur.execute("""
        SELECT iso_code, status, low_poly_url IS NOT NULL as has_lod
        FROM blocks
        WHERE NOT is_archived 
        AND low_poly_url IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 5;
    """)
    ready_blocks = cur.fetchall()
    
    print("✅ BLOCKS READY FOR DASHBOARD (with LOD):")
    if ready_blocks:
        for block in ready_blocks:
            print(f"   {block['iso_code']}: status={block['status']}")
    else:
        print("   (none)")
    print()
    
    # Get blocks without LOD but with original file (can be reprocessed)
    cur.execute("""
        SELECT iso_code, status, url_original
        FROM blocks
        WHERE NOT is_archived
        AND low_poly_url IS NULL
        AND url_original IS NOT NULL
        ORDER BY created_at DESC
        LIMIT 5;
    """)
    reprocessable = cur.fetchall()
    
    print("⚠️  BLOCKS WITHOUT LOD (but have .3dm file - can reprocess):")
    if reprocessable:
        for block in reprocessable:
            original_preview = block['url_original'][:60] + "..." if block['url_original'] else "None"
            print(f"   {block['iso_code']}: {original_preview}")
    else:
        print("   (none)")
    print()
    
    # Get blocks without original file (cannot be reprocessed)
    cur.execute("""
        SELECT iso_code, status, created_at
        FROM blocks
        WHERE NOT is_archived
        AND url_original IS NULL
        ORDER BY created_at DESC
        LIMIT 10;
    """)
    orphaned = cur.fetchall()
    
    print("❌ BLOCKS WITHOUT ORIGINAL FILE (cannot reprocess):")
    if orphaned:
        for block in orphaned:
            print(f"   {block['iso_code']}: status={block['status']}, created={block['created_at']}")
        print()
        print(f"   💡 These blocks were likely created manually for testing.")
        print(f"   💡 They CANNOT appear in dashboard without uploading .3dm files.")
    else:
        print("   (none)")
    print()
    
    cur.close()
    conn.close()
    
    # Recommendations
    print("=" * 70)
    print("📋 RECOMMENDATIONS")
    print("=" * 70)
    
    if stats['with_low_poly'] == 0:
        print("⚠️  NO blocks have LOD geometry. Dashboard will be empty.")
        print()
        print("   To fix:")
        print("   1. Upload a .3dm file via: http://localhost:5173/upload")
        print("   2. Wait ~30 seconds for processing")
        print("   3. Check dashboard: http://localhost:5173/")
        print()
    
    if stats['total'] - stats['with_original'] > 0:
        print(f"⚠️  {stats['total'] - stats['with_original']} blocks have no original file.")
        print("   These were created manually and cannot be processed.")
        print("   Consider cleaning them up:")
        print("   ")
        print("   docker compose run --rm backend python -c \"")
        print("   from infra.supabase_client import get_supabase_client")
        print("   client = get_supabase_client()")
        print("   result = client.table('blocks').delete().is_('url_original', 'null').execute()")
        print("   print(f'Deleted {len(result.data)} blocks without original files')")
        print("   \"")
        print()
    
    if reprocessable:
        print(f"✅ {len(reprocessable)} blocks can be reprocessed with:")
        print("   python infra/reprocess_lod_assets.py --yes --no-monitor")
        print()


if __name__ == "__main__":
    database_url = load_config()
    diagnose_blocks(database_url)
