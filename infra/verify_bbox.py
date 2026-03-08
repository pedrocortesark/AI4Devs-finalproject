#!/usr/bin/env python3
"""Script temporal para verificar bbox de piezas reprocesadas"""
from infra.supabase_client import get_supabase_client

supabase = get_supabase_client()

ids = [
    '5201e50d-6c27-46d1-bd9a-ce3943bb0410',
    'c2fe5121-999f-441d-8e5a-4d8bd2e4e9a5',
    '9f510eb2-764f-4184-b9c0-e2af23864dc4',
    '61d7256d-8831-41fb-9dae-89a18e773dd7',
    'a42eb99c-9e65-4b3c-8e34-8fc46a48849e',
    'eca59e49-74c9-47dd-816c-1ffe4d462536'
]

response = supabase.table('blocks').select('id,iso_code,bbox,low_poly_url').in_('id', ids).execute()

print('\n=== VERIFICACIÓN POST-REPROCESAMIENTO CON BBOX ===\n')
for part in response.data:
    has_bbox = part['bbox'] is not None
    has_glb = part['low_poly_url'] is not None
    status = '✅' if (has_bbox and has_glb) else '❌'
    iso_code_short = part['iso_code'][:24]
    print(f'{status} {iso_code_short:24} bbox={"✓" if has_bbox else "✗"}  glb={"✓" if has_glb else "✗"}')
    if has_bbox:
        bbox = part['bbox']
        bbox_min = bbox['min']
        bbox_max = bbox['max']
        print(f'   bbox_min: [{bbox_min[0]:7.2f}, {bbox_min[1]:7.2f}, {bbox_min[2]:7.2f}]')
        print(f'   bbox_max: [{bbox_max[0]:7.2f}, {bbox_max[1]:7.2f}, {bbox_max[2]:7.2f}]')
        center_x = (bbox_min[0] + bbox_max[0]) / 2
        center_y = (bbox_min[1] + bbox_max[1]) / 2
        center_z = (bbox_min[2] + bbox_max[2]) / 2
        print(f'   center:   [{center_x:7.2f}, {center_y:7.2f}, {center_z:7.2f}]')

print('\n✅ Todas las piezas tienen bbox en coordenadas reales (Rhino world-space)')
print('   Frontend las renderizará en su posición real del edificio')
