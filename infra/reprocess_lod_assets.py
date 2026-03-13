#!/usr/bin/env python3
"""
Script de Reprocesamiento LOD: US-015 Multi-Level LOD System

Este script regenera assets LOD para elementos existentes que solo tienen low_poly_url.
Tras implementar sistema LOD completo:
- Backend ahora genera 3 niveles: high_poly (~7k tris), mid_poly (~2k tris), low_poly (~500 tris)
- Base de datos tiene nuevas columnas: high_poly_url, mid_poly_url
- Frontend usa 4 niveles: high (0-5m), mid (5-20m), low (20-50m), bbox (>50m)

USO:
    python infra/reprocess_lod_assets.py [--dry-run] [--limit N]

OPCIONES:
    --dry-run    Mostrar elementos a reprocesar sin ejecutar
    --limit N    Procesar solo los primeros N elementos (default: todos)

REQUERIMIENTOS:
    - CELERY_BROKER_URL: Redis connection string (para encolar tareas)
    - SUPABASE_DATABASE_URL: PostgreSQL connection string

PROCESO:
    1. Conecta a PostgreSQL (Supabase)
    2. Busca elementos con url_original pero sin high_poly_url o mid_poly_url
    3. Resetea low_poly_url = NULL (forzar regeneración con nuevo código)
    4. Encola generate_low_poly_glb para cada elemento
    5. Worker reprocesará generando los 3 niveles LOD

CONTEXTO:
    User Story: US-015 (LOD System)
    Migration: 20260311000001_lod_system_multi_level.sql
    Fecha implementación: 2026-03-11
    Archivos modificados:
    - supabase/migrations/20260311000001_lod_system_multi_level.sql (DB schema)
    - src/agent/constants.py (LOD_DECIMATION_TARGETS)
    - src/agent/tasks/geometry_processing.py (_generate_lod_glbs, _update_block_lod_urls)
    - src/frontend/src/components/Dashboard/ElementMesh.tsx (4-level LOD component)
"""
import os
import sys
import time
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
from dotenv import load_dotenv

# Add parent directory to path to import modules if needed
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import psycopg2
except ImportError:
    print("❌ ERROR: psycopg2-binary not installed")
    print("   Run: pip install psycopg2-binary")
    print("   Or: docker compose run --rm backend pip install psycopg2-binary")
    sys.exit(1)

try:
    from celery import Celery
except ImportError:
    print("❌ ERROR: celery not installed")
    print("   Run: pip install celery")
    print("   Or: docker compose run --rm backend pip install celery")
    sys.exit(1)


def load_configuration() -> Tuple[str, str]:
    """Load environment variables (12-Factor App pattern)"""
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    load_dotenv(env_file)  # Silent if file doesn't exist

    # Get database URL
    database_url = os.getenv("SUPABASE_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        print("❌ ERROR: Database connection string not found")
        print("   Missing environment variable: SUPABASE_DATABASE_URL or DATABASE_URL")
        print("")
        print("   Add to .env file or environment:")
        print("   SUPABASE_DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres")
        sys.exit(1)

    # Get Celery broker URL
    broker_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")

    return database_url, broker_url


def find_elements_needing_lod(cursor, limit: int = None) -> Dict[str, str]:
    """
    Encuentra elementos que necesitan regeneración LOD
    
    Criterios:
    - Tienen url_original (archivo fuente disponible)
    - Les falta al menos uno de los 3 niveles LOD (high/mid/low)
    
    Args:
        cursor: psycopg2 cursor
        limit: Maximum number of elements to process (None = all)
    
    Returns:
        dict: {block_id: (url_original, iso_code)} para elementos a reprocesar
    """
    print("🔍 Buscando elementos con LOD incompleto...")

    query = """
    SELECT id, url_original, iso_code, low_poly_url, mid_poly_url, high_poly_url, material_type
    FROM blocks
    WHERE url_original IS NOT NULL
      AND (low_poly_url IS NULL OR mid_poly_url IS NULL OR high_poly_url IS NULL)
    ORDER BY iso_code
    """

    if limit:
        query += f" LIMIT {limit}"

    cursor.execute(query)
    rows = cursor.fetchall()

    if not rows:
        print("✅ No hay elementos que requieran reprocesamiento LOD")
        print("   Todos los elementos ya tienen high_poly_url y mid_poly_url")
        return {}

    print(f"\n📊 Encontrados {len(rows)} elementos con LOD incompleto:")
    print(f"{'ISO Code':<15} {'ID':<10} {'Material':<12} {'LOD Status':<30}")
    print("-" * 75)

    elements_to_process = {}
    
    for row in rows:
        block_id, url_original, iso_code, low_poly_url, mid_poly_url, high_poly_url, material_type = row
        
        # LOD status indicators
        low_status = "✓" if low_poly_url else "✗"
        mid_status = "✓" if mid_poly_url else "✗"
        high_status = "✓" if high_poly_url else "✗"
        lod_status = f"low:{low_status} mid:{mid_status} high:{high_status}"
        
        print(f"{iso_code:<15} {block_id[:8]:<10} {material_type or 'unknown':<12} {lod_status:<30}")
        
        elements_to_process[block_id] = (url_original, iso_code)

    return elements_to_process


def reset_lod_urls(cursor, block_ids: List[str]) -> None:
    """
    Resetea low_poly_url = NULL para forzar regeneración completa LOD
    
    Esto fuerza al worker a regenerar los 3 niveles (high/mid/low) con el código nuevo
    que genera múltiples GLBs en lugar de solo uno.
    
    Args:
        cursor: psycopg2 cursor
        block_ids: list of block UUIDs to reset
    """
    print(f"\n🔄 Reseteando {len(block_ids)} elementos (low_poly_url → NULL)...")
    print("   Esto forzará regeneración completa de high/mid/low GLBs")

    placeholders = ",".join(["%s"] * len(block_ids))
    query = f"""
    UPDATE blocks
    SET low_poly_url = NULL,
        mid_poly_url = NULL,
        high_poly_url = NULL
    WHERE id IN ({placeholders})
    """

    cursor.execute(query, block_ids)
    print(f"   ✅ {cursor.rowcount} registros actualizados")


def enqueue_lod_generation_tasks(celery_app: Celery, elements: Dict[str, Tuple[str, str]]) -> List[str]:
    """
    Encola tareas de generación LOD para cada elemento
    
    Args:
        celery_app: Celery application instance
        elements: dict {block_id: (url_original, iso_code)}
    
    Returns:
        list: Task IDs for monitoring
    """
    print(f"\n🚀 Encolando {len(elements)} tareas de generación LOD...")

    task_ids = []
    
    for i, (block_id, (url_original, iso_code)) in enumerate(elements.items(), 1):
        try:
            # Send task to queue
            # Task signature: generate_low_poly_glb(block_id: str)
            # The task fetches url_original from DB internally
            # Despite the name "low_poly", this task now generates all 3 LOD levels
            # Task registered as "agent.generate_low_poly_glb" in worker (see celery logs)
            result = celery_app.send_task(
                "agent.generate_low_poly_glb",
                args=[block_id],  # Only pass block_id, task fetches url_original from DB
                queue="celery"  # Worker listens on "celery" queue
            )
            
            task_ids.append(result.id)
            print(f"   [{i}/{len(elements)}] {iso_code} ({block_id[:8]}): task_id={result.id[:8]}")
            
        except Exception as e:
            print(f"   ❌ Error encolando {iso_code}: {e}")

    return task_ids


def monitor_task_progress(celery_app: Celery, task_ids: List[str], timeout: int = 600) -> None:
    """
    Monitorea progreso de las tareas encoladas
    
    Args:
        celery_app: Celery application instance
        task_ids: List of task IDs to monitor
        timeout: Maximum time to wait in seconds (default 10 minutes)
    """
    if not task_ids:
        return

    print(f"\n⏳ Monitoreando {len(task_ids)} tareas (timeout: {timeout}s)...")
    print("   Presiona Ctrl+C para salir (las tareas continuarán en el worker)")

    start_time = time.time()
    status_counts = {"PENDING": len(task_ids), "SUCCESS": 0, "FAILURE": 0, "RUNNING": 0}

    try:
        while time.time() - start_time < timeout:
            status_counts = {"PENDING": 0, "SUCCESS": 0, "FAILURE": 0, "RUNNING": 0, "OTHER": 0}
            
            for task_id in task_ids:
                result = celery_app.AsyncResult(task_id)
                status = result.state
                status_counts[status if status in status_counts else "OTHER"] += 1

            # Print status summary
            elapsed = int(time.time() - start_time)
            print(f"\r   [{elapsed}s] SUCCESS: {status_counts['SUCCESS']}/{len(task_ids)} | "
                  f"RUNNING: {status_counts['RUNNING']} | "
                  f"PENDING: {status_counts['PENDING']} | "
                  f"FAILURE: {status_counts['FAILURE']}", end="", flush=True)

            # Check if all tasks completed
            if status_counts["PENDING"] == 0 and status_counts["RUNNING"] == 0:
                print("\n")
                if status_counts["FAILURE"] > 0:
                    print(f"⚠️  {status_counts['FAILURE']} tareas fallaron")
                    print("   Revisa logs del worker para detalles: docker compose logs agent-worker")
                else:
                    print("✅ Todas las tareas completadas exitosamente")
                break

            time.sleep(5)  # Poll every 5 seconds
        else:
            # Timeout reached
            print(f"\n⚠️  Timeout alcanzado ({timeout}s)")
            print("   Las tareas continuarán ejecutándose en el worker")
            print("   Verifica estado en logs: docker compose logs agent-worker -f")

    except KeyboardInterrupt:
        print("\n\n⚠️  Monitoreo cancelado (Ctrl+C)")
        print("   Las tareas continuarán ejecutándose en el worker")


def main():
    """Main execution flow"""
    parser = argparse.ArgumentParser(
        description="Reprocesar elementos para generar assets LOD completos (high/mid/low)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mostrar elementos a reprocesar sin ejecutar cambios"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Procesar solo los primeros N elementos (default: todos)"
    )
    parser.add_argument(
        "--no-monitor",
        action="store_true",
        help="No monitorear progreso de tareas (solo encolar y salir)"
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Auto-confirmar sin prompt interactivo"
    )

    args = parser.parse_args()

    print("=" * 80)
    print(" 🎨 US-015: LOD Asset Reprocessing Script")
    print("=" * 80)
    print()

    # Load configuration
    database_url, broker_url = load_configuration()
    print(f"✅ Configuración cargada:")
    print(f"   Database: {database_url.split('@')[1] if '@' in database_url else 'configured'}")
    print(f"   Broker: {broker_url}")
    print()

    # Connect to database
    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        print("✅ Conectado a PostgreSQL (Supabase)")
    except Exception as e:
        print(f"❌ Error conectando a base de datos: {e}")
        sys.exit(1)

    try:
        # Find elements needing LOD reprocessing
        elements = find_elements_needing_lod(cursor, limit=args.limit)

        if not elements:
            print("\n🎉 No hay elementos para reprocesar. Sistema LOD completo.")
            return

        if args.dry_run:
            print(f"\n🔍 DRY RUN: Se reprocesarían {len(elements)} elementos")
            print("   Ejecuta sin --dry-run para aplicar cambios")
            return

        # Confirm action
        if not args.yes:
            print(f"\n⚠️  Esto reprocesará {len(elements)} elementos:")
            print("   1. Resetear low_poly_url a NULL")
            print("   2. Encolar tareas de generación LOD")
            print("   3. Worker generará high/mid/low GLBs")
            response = input("\n¿Continuar? (yes/no): ").strip().lower()

            if response not in ["yes", "y"]:
                print("❌ Operación cancelada por el usuario")
                return

        # Reset LOD URLs
        reset_lod_urls(cursor, list(elements.keys()))
        conn.commit()

        # Initialize Celery app
        celery_app = Celery("agent", broker=broker_url)

        # Enqueue tasks
        task_ids = enqueue_lod_generation_tasks(celery_app, elements)

        if task_ids and not args.no_monitor:
            monitor_task_progress(celery_app, task_ids, timeout=600)

        print("\n" + "=" * 80)
        print("✅ Reprocesamiento LOD iniciado")
        print("=" * 80)
        print()
        print("📊 Para verificar resultados:")
        print("   1. Revisa logs del worker: docker compose logs agent-worker -f")
        print("   2. Verifica DB (high_poly_url, mid_poly_url poblados)")
        print("   3. Inspecciona Supabase Storage buckets:")
        print("      - high-poly/ (~600-800KB GLB)")
        print("      - mid-poly/  (~300-400KB GLB)")
        print("      - low-poly/  (~150-200KB GLB)")
        print()

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
