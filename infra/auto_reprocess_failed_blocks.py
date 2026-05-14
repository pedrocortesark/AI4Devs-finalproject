#!/usr/bin/env python3
"""
Auto-Reprocess Failed Blocks - SF-PM Processing Recovery Tool

Este script identifica y reprocesa automáticamente bloques que no completaron
su pipeline de procesamiento, específicamente aquellos que:
  - Tienen status='validated' pero NO tienen geometría LOD
  - Tienen status='processing' hace más de 1 hora (atorados)
  - Tienen url_original pero les falta high/mid/low_poly_url

USO:
    # Modo interactivo (requiere confirmación):
    python infra/auto_reprocess_failed_blocks.py
    
    # Modo automático (sin confirmación):
    python infra/auto_reprocess_failed_blocks.py --yes
    
    # Ver qué se procesaría sin ejecutar:
    python infra/auto_reprocess_failed_blocks.py --dry-run
    
    # Procesar solo los primeros N bloques:
    python infra/auto_reprocess_failed_blocks.py --limit 50

CONTEXTO:
    Cuando se suben archivos .3dm con múltiples bloques, el pipeline es:
    1. upload → register_3dm_blocks (crea N bloques, uno por InstanceDefinition)
    2. validate_file (valida nomenclatura + geometría) → status='validated'
    3. generate_low_poly_glb (genera LOD en 3 niveles) → actualiza URLs
    
    Este script detecta bloques que se atoraron entre paso 2 y 3.

SALIDA:
    Encola tareas Celery de `generate_low_poly_glb` para cada bloque sin procesar.
    El worker Celery debe estar corriendo para ejecutar las tareas.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
import argparse
from urllib.parse import quote_plus

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from infra.supabase_client import get_supabase_client

try:
    from celery import Celery
    import os
except ImportError:
    print("❌ ERROR: celery not installed")
    sys.exit(1)


def get_celery_app():
    """Initialize Celery client with proper Redis authentication"""
    # Build broker URL with same logic as src/backend/config.py
    redis_password = os.getenv("REDIS_PASSWORD", "")
    redis_host = os.getenv("REDIS_HOST", "redis")
    redis_port = os.getenv("REDIS_PORT", "6379")
    redis_db = os.getenv("REDIS_DB", "0")
    
    # URL-encode password to handle special characters
    if redis_password:
        encoded_password = quote_plus(redis_password)
        broker_url = f"redis://:{encoded_password}@{redis_host}:{redis_port}/{redis_db}"
    else:
        broker_url = f"redis://{redis_host}:{redis_port}/{redis_db}"
    
    app = Celery('sf-pm', broker=broker_url)
    return app


def find_stuck_blocks(client):
    """
    Encuentra bloques atorados en el pipeline.
    
    Returns:
        List of dicts with block info: id, iso_code, status, created_at
    """
    # Fetch all blocks that need processing
    response = client.table('blocks').select(
        'id, iso_code, status, url_original, low_poly_url, mid_poly_url, high_poly_url, created_at'
    ).execute()
    
    blocks = response.data
    stuck_blocks = []
    
    now = datetime.now(timezone.utc)
    one_hour_ago = now - timedelta(hours=1)
    
    for block in blocks:
        # Case 1: validated but no LOD
        if (block.get('status') == 'validated' and 
            block.get('url_original') and 
            not block.get('low_poly_url')):
            stuck_blocks.append(block)
            continue
        
        # Case 2: processing for more than 1 hour
        if block.get('status') == 'processing' and block.get('url_original'):
            created_str = block.get('created_at')
            if created_str:
                created = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
                if created < one_hour_ago:
                    stuck_blocks.append(block)
    
    return stuck_blocks


def reprocess_blocks(block_ids: list, dry_run: bool = False):
    """Encola tareas de reprocesamiento para los bloques dados"""
    if not block_ids:
        print("✅ No hay bloques para reprocesar")
        return 0
    
    if dry_run:
        print(f"\n🔍 DRY RUN: Se encolarían {len(block_ids)} tareas")
        return 0
    
    celery_app = get_celery_app()
    enqueued = 0
    
    print(f"\n📤 Encolando {len(block_ids)} tareas...")
    for block_id in block_ids:
        try:
            celery_app.send_task(
                'agent.generate_low_poly_glb',  # IMPORTANT: Task name without .tasks
                args=[block_id]
            )
            enqueued += 1
            if enqueued % 10 == 0:
                print(f"   Encoladas {enqueued}/{len(block_ids)} tareas...")
        except Exception as e:
            print(f"❌ Error encolando block {block_id}: {e}")
    
    return enqueued


def main():
    parser = argparse.ArgumentParser(
        description='Reprocesar bloques atorados en el pipeline'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Mostrar bloques a reprocesar sin ejecutar'
    )
    parser.add_argument(
        '--yes',
        action='store_true',
        help='Procesar sin pedir confirmación'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Procesar solo los primeros N bloques'
    )
    
    args = parser.parse_args()
    
    print('=' * 70)
    print('🔧 SF-PM: Auto-Reprocess Failed Blocks')
    print('=' * 70)
    
    # Connect to database
    client = get_supabase_client()
    
    # Find stuck blocks
    print('\n🔍 Buscando bloques atorados...')
    stuck_blocks = find_stuck_blocks(client)
    
    if not stuck_blocks:
        print('\n✅ No hay bloques atorados. Sistema funcionando correctamente.')
        return
    
    # Apply limit if specified
    if args.limit:
        stuck_blocks = stuck_blocks[:args.limit]
    
    # Show summary
    print(f'\n⚠️  Bloques atorados encontrados: {len(stuck_blocks)}')
    print('\n📋 Resumen:')
    
    # Group by status
    by_status = {}
    for block in stuck_blocks:
        status = block.get('status', 'unknown')
        by_status[status] = by_status.get(status, 0) + 1
    
    for status, count in sorted(by_status.items(), key=lambda x: -x[1]):
        print(f'  {status:20s}: {count:4d} bloques')
    
    # Show examples
    print(f'\n📦 Ejemplos de bloques a reprocesar (primeros 10):')
    for block in stuck_blocks[:10]:
        iso = block.get('iso_code', 'N/A')[:50]
        status = block.get('status', 'N/A')
        created = block.get('created_at', 'N/A')[:19] if block.get('created_at') else 'N/A'
        print(f'  {iso:50s} | {status:15s} | {created}')
    
    if args.dry_run:
        print(f'\n🔍 DRY RUN: No se encolará ninguna tarea')
        print(f'   Para reprocesar, ejecuta sin --dry-run')
        return
    
    # Ask for confirmation unless --yes
    if not args.yes:
        print(f'\n⚠️  Esto encolará {len(stuck_blocks)} tareas de reprocesamiento.')
        print(f'   El worker Celery debe estar corriendo.')
        response = input('\n¿Continuar? (yes/no): ')
        if response.lower() not in ['yes', 'y', 'si', 'sí']:
            print('❌ Operación cancelada')
            return
    
    # Reprocess
    block_ids = [b['id'] for b in stuck_blocks]
    enqueued = reprocess_blocks(block_ids, dry_run=args.dry_run)
    
    print(f'\n✅ {enqueued} tareas encoladas exitosamente')
    print(f'\n💡 Monitorea el progreso con:')
    print(f'   docker compose logs agent-worker -f --tail 50')
    print(f'\n💡 O verifica el dashboard después de unos minutos.')
    print()


if __name__ == '__main__':
    main()
