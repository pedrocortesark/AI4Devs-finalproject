#!/usr/bin/env python3
"""
Diagnose block processing status.

Analyzes all blocks in the database to identify why some are not fully processed.
Provides statistics on status distribution, geometry processing, and validation errors.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from infra.supabase_client import get_supabase_client
import json


def main():
    client = get_supabase_client()
    
    # Fetch all blocks with relevant fields
    response = client.table('blocks').select(
        'id, iso_code, status, tipologia, low_poly_url, mid_poly_url, high_poly_url, '
        'validation_report, bbox, created_at, updated_at'
    ).execute()
    
    blocks = response.data
    total = len(blocks)
    
    if total == 0:
        print("❌ No blocks found in database")
        return
    
    # Count by status
    status_counts = {}
    for block in blocks:
        status = block.get('status', 'unknown')
        status_counts[status] = status_counts.get(status, 0) + 1
    
    # Count blocks with geometry (LOD system)
    with_low_poly = len([b for b in blocks if b.get('low_poly_url')])
    with_mid_poly = len([b for b in blocks if b.get('mid_poly_url')])
    with_high_poly = len([b for b in blocks if b.get('high_poly_url')])
    with_bbox = len([b for b in blocks if b.get('bbox')])
    
    # Count blocks with validation errors
    with_errors = 0
    error_types = {}
    rejected_reasons = []
    
    for block in blocks:
        vr = block.get('validation_report')
        if vr and isinstance(vr, dict):
            errors = vr.get('errors', [])
            if errors:
                with_errors += 1
                for error in errors:
                    error_type = error.get('type', 'unknown')
                    error_types[error_type] = error_types.get(error_type, 0) + 1
                    
                    # Track rejected blocks with their ISO codes
                    if block.get('status') == 'rejected':
                        rejected_reasons.append({
                            'iso_code': block.get('iso_code', 'N/A')[:40],
                            'error_type': error_type,
                            'message': error.get('message', 'N/A')[:60]
                        })
    
    # Print report
    print('=' * 70)
    print('📊 DIAGNÓSTICO DE PROCESAMIENTO DE BLOQUES')
    print('=' * 70)
    
    print(f'\n🔢 TOTAL DE BLOQUES: {total}')
    print(f'\n📦 GEOMETRÍA PROCESADA (LOD System):')
    print(f'   Low-Poly (visualización):  {with_low_poly:4d} / {total} ({with_low_poly*100//total if total > 0 else 0}%)')
    print(f'   Mid-Poly (detalle):        {with_mid_poly:4d} / {total} ({with_mid_poly*100//total if total > 0 else 0}%)')
    print(f'   High-Poly (alta calidad):  {with_high_poly:4d} / {total} ({with_high_poly*100//total if total > 0 else 0}%)')
    print(f'   BBox (bounding box):       {with_bbox:4d} / {total} ({with_bbox*100//total if total > 0 else 0}%)')
    
    print(f'\n📈 DISTRIBUCIÓN POR STATUS:')
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        percentage = (count * 100 // total) if total > 0 else 0
        emoji = {
            'uploaded': '⏳',
            'validated': '✅',
            'rejected': '❌',
            'error_processing': '🔥',
            'archived': '📦'
        }.get(status, '❓')
        print(f'   {emoji} {status:20s}: {count:4d} bloques ({percentage:3d}%)')
    
    if with_errors > 0:
        print(f'\n⚠️  BLOQUES CON ERRORES DE VALIDACIÓN: {with_errors}')
        print(f'\n   Tipos de error encontrados:')
        for error_type, count in sorted(error_types.items(), key=lambda x: -x[1]):
            print(f'      • {error_type}: {count} bloques')
    
    # Show sample rejected blocks
    if rejected_reasons:
        print(f'\n❌ BLOQUES RECHAZADOS (primeros 10):')
        for item in rejected_reasons[:10]:
            print(f"   - {item['iso_code']:40s} | {item['error_type']:20s}")
            print(f"     └─ {item['message']}")
    
    # Show examples of blocks without geometry
    no_geometry = [b for b in blocks if not b.get('low_poly_url')]
    if no_geometry:
        print(f'\n🔍 BLOQUES SIN GEOMETRÍA PROCESADA: {len(no_geometry)} bloques')
        print(f'\n   Ejemplos (primeros 10):')
        for block in no_geometry[:10]:
            iso = block.get('iso_code', 'N/A')[:40]
            status = block.get('status', 'N/A')
            created = block.get('created_at', 'N/A')[:19] if block.get('created_at') else 'N/A'
            print(f'   - {iso:40s} | status: {status:20s} | created: {created}')
    
    # Summary and recommendations
    print(f'\n' + '=' * 70)
    print('📋 RESUMEN Y RECOMENDACIONES')
    print('=' * 70)
    
    processing_rate = (with_low_poly * 100 // total) if total > 0 else 0
    print(f'\n✅ Tasa de procesamiento exitoso: {processing_rate}%')
    
    if processing_rate < 50:
        print(f'\n⚠️  ALERTA: Menos del 50% de los bloques han sido procesados')
        print(f'\n   Posibles causas:')
        print(f'   1. Worker de Celery no está corriendo o no tiene capacidad suficiente')
        print(f'   2. Errores en la geometría de los archivos .3dm')
        print(f'   3. Timeouts en el procesamiento (archivos muy grandes)')
        print(f'   4. Errores en la validación de nomenclatura')
        print(f'\n   Acciones sugeridas:')
        print(f'   • Verificar logs del worker: docker compose logs agent-worker --tail 100')
        print(f'   • Reprocesar bloques fallidos: python infra/reprocess_lod_assets.py')
        print(f'   • Revisar archivos .3dm manualmente en Rhino')
    
    elif processing_rate < 80:
        print(f'\n⚠️  ATENCIÓN: {100 - processing_rate}% de bloques sin procesar')
        print(f'\n   Acciones sugeridas:')
        print(f'   • Reprocesar bloques pendientes: python infra/reprocess_lod_assets.py')
        print(f'   • Revisar logs para errores específicos')
    
    else:
        print(f'\n✅ Sistema funcionando correctamente')
        print(f'   • {processing_rate}% de bloques procesados exitosamente')
    
    print()


if __name__ == '__main__':
    main()
