#!/usr/bin/env python3
"""
Analyze blocks stuck in processing.

Identifies blocks that have been validated but don't have geometry processed,
which indicates the Celery task queue may have issues.
"""

import sys
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from infra.supabase_client import get_supabase_client


def main():
    client = get_supabase_client()
    
    # Fetch all blocks
    response = client.table('blocks').select(
        'id, iso_code, status, url_original, low_poly_url, created_at, updated_at'
    ).execute()
    
    blocks = response.data
    total = len(blocks)
    
    print(f'📊 Total bloques en DB: {total}\n')
    
    # Count by status
    status_counter = Counter(b.get('status') for b in blocks)
    print('📈 Distribución por STATUS:')
    for status, count in status_counter.most_common():
        pct = (count * 100 // total) if total > 0 else 0
        print(f'  {status:20s}: {count:4d} ({pct:3d}%)')
    
    # Count geometry processed
    total_with_3dm = sum(1 for b in blocks if b.get('url_original'))
    total_with_lod = sum(1 for b in blocks if b.get('low_poly_url'))
    
    print(f'\n📦 Geometría:')
    print(f'  Bloques con .3dm original:  {total_with_3dm:4d} ({total_with_3dm*100//total if total > 0 else 0}%)')
    print(f'  Bloques con LOD procesado:  {total_with_lod:4d} ({total_with_lod*100//total if total > 0 else 0}%)')
    
    # Find problematic blocks: validated but no LOD
    validated_no_lod = [
        b for b in blocks 
        if b.get('status') == 'validated' 
        and not b.get('low_poly_url') 
        and b.get('url_original')
    ]
    
    print(f'\n⚠️  PROBLEMA DETECTADO:')
    print(f'  Bloques con status=validated pero SIN geometría LOD: {len(validated_no_lod)}')
    
    if not validated_no_lod:
        print('\n✅ No hay bloques atorados. Sistema funcionando correctamente.')
        return
    
    print(f'\n  Estos bloques pasaron la validación pero la tarea de geometría')
    print(f'  (generate_low_poly_glb) nunca se completó.')
    
    # Analyze timing
    now = datetime.now(timezone.utc)
    old_blocks = []
    
    for block in validated_no_lod:
        created_str = block.get('created_at')
        if created_str:
            created = datetime.fromisoformat(created_str.replace('Z', '+00:00'))
            age_hours = (now - created).total_seconds() / 3600
            if age_hours > 1:  # Older than 1 hour
                old_blocks.append({
                    'iso_code': block['iso_code'],
                    'created': created_str,
                    'age_hours': int(age_hours)
                })
    
    if old_blocks:
        print(f'\n🕐 Bloques atorados hace más de 1 hora: {len(old_blocks)}')
        print(f'\n  Ejemplos (primeros 15):')
        for block in old_blocks[:15]:
            print(f"    {block['iso_code'][:50]:50s} | {block['age_hours']:3d}h ago")
    
    # Recommendations
    print('\n' + '=' * 70)
    print('💡 CAUSA RAÍZ IDENTIFICADA:')
    print('=' * 70)
    print('\n  Las tareas de Celery `generate_low_poly_glb` no se están ejecutando.')
    print('\n  Posibles causas:')
    print('  1. El worker no está procesando tareas (verificar logs)')
    print('  2. Redis perdió las tareas encoladas (reinicio inesperado)')
    print('  3. Las tareas fallaron silenciosamente sin actualizar status')
    print('  4. Timeout en tareas muy pesadas (archivos grandes)')
    
    print('\n' + '=' * 70)
    print('🔧 SOLUCIÓN:')
    print('=' * 70)
    print('\n  Para reprocesar TODOS los bloques sin geometría:')
    print('\n    docker compose run --rm backend python /app/infra/reprocess_lod_assets.py --yes --no-monitor')
    print('\n  Esto encolará nuevas tareas para cada bloque sin LOD.')
    print(f'\n  Aproximadamente {len(validated_no_lod)} bloques serán reprocesados.')
    print()


if __name__ == '__main__':
    main()
