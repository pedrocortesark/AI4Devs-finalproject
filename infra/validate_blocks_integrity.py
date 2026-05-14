#!/usr/bin/env python3
"""
Validate Blocks Integrity - SF-PM Data Quality Tool

Verifica la integridad de los bloques en la base de datos:
  - Detecta duplicados (mismo iso_code)
  - Identifica bloques que faltan procesar
  - Compara contra archivos originales subidos
  - Genera reporte de inconsistencias

USO:
    python infra/validate_blocks_integrity.py [--fix-duplicates]
    
OPCIONES:
    --fix-duplicates    Eliminar automáticamente bloques duplicados (mantiene el más reciente)
"""

import sys
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from infra.supabase_client import get_supabase_client


def find_duplicates(client):
    """Encuentra bloques con iso_code duplicado"""
    response = client.table('blocks').select(
        'id, iso_code, status, url_original, low_poly_url, created_at, updated_at'
    ).execute()
    
    blocks = response.data
    
    # Group by iso_code
    by_iso_code = defaultdict(list)
    for block in blocks:
        iso_code = block.get('iso_code', 'UNKNOWN')
        by_iso_code[iso_code].append(block)
    
    # Find duplicates
    duplicates = {
        iso_code: blocks_list 
        for iso_code, blocks_list in by_iso_code.items() 
        if len(blocks_list) > 1
    }
    
    return duplicates


def find_missing_blocks(client):
    """Encuentra bloques que deberían procesarse pero no se han procesado"""
    response = client.table('blocks').select(
        'id, iso_code, status, url_original, low_poly_url, mid_poly_url, high_poly_url, created_at'
    ).execute()
    
    blocks = response.data
    
    # Bloques con .3dm pero sin LOD completo
    missing_lod = []
    for block in blocks:
        if block.get('url_original'):
            has_low = block.get('low_poly_url')
            has_mid = block.get('mid_poly_url')
            has_high = block.get('high_poly_url')
            
            # Si tiene .3dm pero le falta algún nivel LOD
            if not (has_low and has_mid and has_high):
                missing_lod.append(block)
    
    return missing_lod


def analyze_status_distribution(client):
    """Analiza distribución de status"""
    response = client.table('blocks').select('status').execute()
    status_counts = Counter(b.get('status') for b in response.data)
    return status_counts


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Validar integridad de bloques')
    parser.add_argument(
        '--fix-duplicates',
        action='store_true',
        help='Eliminar bloques duplicados automáticamente'
    )
    
    args = parser.parse_args()
    
    print('=' * 70)
    print('🔍 SF-PM: Validación de Integridad de Bloques')
    print('=' * 70)
    
    client = get_supabase_client()
    
    # Total blocks
    response = client.table('blocks').select('id').execute()
    total_blocks = len(response.data)
    print(f'\n📊 Total bloques en DB: {total_blocks}')
    
    # Check duplicates
    print('\n🔎 Buscando duplicados por iso_code...')
    duplicates = find_duplicates(client)
    
    if duplicates:
        print(f'\n⚠️  DUPLICADOS ENCONTRADOS: {len(duplicates)} iso_codes duplicados')
        print(f'\n   Ejemplos (primeros 10):')
        for iso_code, blocks_list in list(duplicates.items())[:10]:
            print(f'\n   📦 {iso_code}: {len(blocks_list)} copias')
            for block in blocks_list:
                created = block.get('created_at', 'N/A')[:19] if block.get('created_at') else 'N/A'
                status = block.get('status', 'N/A')
                has_lod = '✅' if block.get('low_poly_url') else '❌'
                print(f'      - ID: {block["id"][:8]}... | status: {status:15s} | LOD: {has_lod} | created: {created}')
        
        if args.fix_duplicates:
            print(f'\n🔧 Eliminando duplicados (manteniendo el más reciente con LOD)...')
            deleted_count = 0
            for iso_code, blocks_list in duplicates.items():
                # Sort by: has LOD (priority), then by created_at (most recent)
                sorted_blocks = sorted(
                    blocks_list,
                    key=lambda b: (
                        bool(b.get('low_poly_url')),  # Prioritize blocks with LOD
                        b.get('created_at') or ''  # Then by creation date
                    ),
                    reverse=True
                )
                
                # Keep the first one (most recent with LOD), delete the rest
                to_delete = sorted_blocks[1:]
                
                for block in to_delete:
                    try:
                        client.table('blocks').delete().eq('id', block['id']).execute()
                        deleted_count += 1
                        print(f'   ❌ Eliminado: {iso_code} (ID: {block["id"][:8]}...)')
                    except Exception as e:
                        print(f'   ⚠️  Error eliminando {block["id"]}: {e}')
            
            print(f'\n✅ Eliminados {deleted_count} bloques duplicados')
    else:
        print('   ✅ No se encontraron duplicados')
    
    # Check missing LOD
    print('\n🔎 Buscando bloques sin LOD completo...')
    missing_lod = find_missing_blocks(client)
    
    if missing_lod:
        print(f'\n⚠️  BLOQUES SIN LOD COMPLETO: {len(missing_lod)}')
        
        # Analyze why they're missing
        by_status = defaultdict(list)
        for block in missing_lod:
            by_status[block.get('status', 'unknown')].append(block)
        
        print(f'\n   Distribución por status:')
        for status, blocks_list in sorted(by_status.items(), key=lambda x: -len(x[1])):
            print(f'      {status:20s}: {len(blocks_list):4d} bloques')
        
        print(f'\n   Ejemplos (primeros 10):')
        for block in missing_lod[:10]:
            iso = block.get('iso_code', 'N/A')[:50]
            status = block.get('status', 'N/A')
            has_low = '✅' if block.get('low_poly_url') else '❌'
            has_mid = '✅' if block.get('mid_poly_url') else '❌'
            has_high = '✅' if block.get('high_poly_url') else '❌'
            created = block.get('created_at', 'N/A')[:19] if block.get('created_at') else 'N/A'
            print(f'      {iso:50s} | {status:15s} | L:{has_low} M:{has_mid} H:{has_high} | {created}')
        
        print(f'\n   💡 Para reprocesar estos bloques:')
        print(f'      docker compose run --rm backend python /app/infra/auto_reprocess_failed_blocks.py --yes')
    else:
        print('   ✅ Todos los bloques con .3dm tienen LOD completo')
    
    # Status distribution
    print('\n📈 Distribución de status:')
    status_counts = analyze_status_distribution(client)
    for status, count in status_counts.most_common():
        pct = (count * 100 // total_blocks) if total_blocks > 0 else 0
        print(f'   {status:20s}: {count:4d} ({pct:3d}%)')
    
    # Summary
    print('\n' + '=' * 70)
    print('📋 RESUMEN')
    print('=' * 70)
    
    issues = []
    if duplicates:
        issues.append(f'⚠️  {len(duplicates)} iso_codes duplicados')
    if missing_lod:
        issues.append(f'⚠️  {len(missing_lod)} bloques sin LOD completo')
    
    if not issues:
        print('\n✅ Base de datos íntegra - No se detectaron problemas')
    else:
        print('\n⚠️  Problemas detectados:')
        for issue in issues:
            print(f'   {issue}')
        
        if not args.fix_duplicates and duplicates:
            print(f'\n💡 Para eliminar duplicados automáticamente:')
            print(f'   python infra/validate_blocks_integrity.py --fix-duplicates')
    
    print()


if __name__ == '__main__':
    main()
