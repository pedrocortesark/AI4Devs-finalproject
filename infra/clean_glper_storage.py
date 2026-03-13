"""
Clean GLPER GLB files from Supabase Storage.

Removes all high-poly, mid-poly, and low-poly GLB files for the 6 GLPER elements.
"""
from infra.supabase_client import get_supabase_client

def clean_glper_storage():
    supabase = get_supabase_client()
    
    # IDs de los elementos GLPER que eliminamos de la DB
    element_ids = [
        'ef868c3b-36c5-4d4e-ac81-bb2f49b4971c',  # GLPER.B-PAE0720.0702
        '4a4805d9-b76c-4d52-8bdd-de32952bf7f0',  # GLPER.B-PAE0720.0704
        'ca11ea52-0918-4772-b8d4-241f02a254fe',  # GLPER.B-PAE0720.0701
        '51fed244-d94a-40aa-8e96-68a9232eaf62',  # GLPER.B-PAE0720.0706
        '57e303c7-150f-4889-b088-e702e38e4f95',  # GLPER.B-PAE0720.0703
        'cc9a8b6f-e4dd-4d9d-8c0c-e5af2d85e8ed',  # GLPER.B-PAE0720.0705
    ]
    
    folders = ['high-poly', 'mid-poly', 'low-poly']
    deleted_count = 0
    
    for folder in folders:
        print(f'\n📂 Cleaning {folder}/ folder...')
        for element_id in element_ids:
            file_path = f'{folder}/{element_id}.glb'
            try:
                supabase.storage.from_('processed-geometry').remove([file_path])
                print(f'  ✓ Deleted {file_path}')
                deleted_count += 1
            except Exception as e:
                error_msg = str(e).lower()
                if 'not found' not in error_msg and 'does not exist' not in error_msg:
                    print(f'  ⚠️ Error deleting {file_path}: {e}')
                else:
                    print(f'  ⊘ {file_path} (already deleted)')
    
    print(f'\n✅ Deleted {deleted_count} GLB files from Supabase Storage')
    return deleted_count

if __name__ == '__main__':
    clean_glper_storage()
