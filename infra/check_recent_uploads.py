#!/usr/bin/env python3
"""
Verifica archivos recientes en Supabase Storage (raw-uploads bucket)
"""
import os
import sys
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from infra.supabase_client import get_supabase_client


def check_recent_uploads():
    """List recent uploads in Supabase Storage"""
    client = get_supabase_client()
    
    print('🗄️  ARCHIVOS EN raw-uploads BUCKET:')
    print('=' * 70)
    
    try:
        # List all folders in uploads/ (cada upload tiene su UUID)
        folders = client.storage.from_('raw-uploads').list(path='uploads')
        
        if not folders:
            print('❌ No hay carpetas en raw-uploads/uploads/')
            print('   El upload desde Vercel NO completó.')
            return False
        
        print(f'📁 Encontradas {len(folders)} carpetas de uploads:')
        print()
        
        # Ordenar por fecha de creación (más recientes primero)
        folders_sorted = sorted(
            folders, 
            key=lambda x: x.get('created_at', ''), 
            reverse=True
        )
        
        # Mostrar últimas 5 carpetas y sus archivos
        for i, folder in enumerate(folders_sorted[:5], 1):
            folder_name = folder.get('name', 'unknown')
            created = folder.get('created_at', 'unknown')
            
            print(f'{i}. 📁 {folder_name}/')
            print(f'   Created: {created}')
            
            # Listar archivos dentro de esta carpeta
            try:
                files = client.storage.from_('raw-uploads').list(path=f'uploads/{folder_name}')
                if files:
                    for f in files:
                        name = f.get('name', 'unknown')
                        metadata = f.get('metadata', {})
                        size = metadata.get('size', 0) if isinstance(metadata, dict) else 0
                        size_mb = size / 1024 / 1024 if size > 0 else 0
                        
                        print(f'      📄 {name} ({size_mb:.2f} MB)')
                else:
                    print(f'      (carpeta vacía)')
            except Exception as e:
                print(f'      ⚠️  Error listando archivos: {e}')
            
            print()
        
        if len(folders_sorted) > 5:
            print(f'... y {len(folders_sorted) - 5} carpetas más antiguas')
        
        print('=' * 70)
        print(f'✅ Total: {len(folders_sorted)} uploads en el bucket')
        return True
        
    except Exception as e:
        print(f'❌ ERROR: {e}')
        return False


if __name__ == '__main__':
    success = check_recent_uploads()
    sys.exit(0 if success else 1)
