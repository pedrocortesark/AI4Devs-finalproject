#!/usr/bin/env python3
"""
Script de Reprocesamiento: Digital Twin Architecture Migration

Este script resetea y re-procesa 6 piezas existentes que fueron procesadas con código viejo
(pre-bbox storage). Tras implementar cambio arquitectónico a coordenadas reales de Rhino:
- Backend ahora guarda bbox absoluto (no centrado en origen)
- Backend aplica rotación Z→Y durante export
- Frontend posiciona por bbox center en lugar de grid artificial

USO:
    python scripts/reprocess_parts_with_bbox.py

REQUERIMIENTOS:
    - CELERY_BROKER_URL: Redis connection string (para encolar tareas)
    - SUPABASE_DATABASE_URL: PostgreSQL connection string

PROCESO:
    1. Conecta a PostgreSQL (Supabase)
    2. Verifica que las 6 piezas tienen url_original
    3. Pone low_poly_url = NULL (bypass idempotency)
    4. Encola generate_low_poly_glb para cada pieza
    5. El worker reprocesará con nuevo código (bbox storage + rotación)

CONTEXTO:
    User Story: US-005 (3D Dashboard)
    Tickets relacionados: T-0502-AGENT (geometry_processing.py), T-0507-FRONT (LOD system)
    Fecha cambio arquitectónico: 2026-03-04
    IDs afectados: 5201e50d, c2fe5121, 9f510eb2, 61d7256d, a42eb99c, eca59e49
"""
import os
import sys
from pathlib import Path
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


# IDs de las 6 piezas procesadas con código viejo (sin bbox storage)
PARTS_TO_REPROCESS = [
    "5201e50d-6c27-46d1-bd9a-ce3943bb0410",
    "c2fe5121-999f-441d-8e5a-4d8bd2e4e9a5",
    "9f510eb2-764f-4184-b9c0-e2af23864dc4",
    "61d7256d-8831-41fb-9dae-89a18e773dd7",
    "a42eb99c-9e65-4b3c-8e34-8fc46a48849e",
    "eca59e49-74c9-47dd-816c-1ffe4d462536",
]


def load_configuration():
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


def verify_parts_exist(cursor):
    """
    Verifica que las 6 piezas existen y tienen url_original

    Returns:
        dict: {block_id: url_original} para piezas válidas
    """
    print("🔍 Verificando piezas en base de datos...")

    placeholders = ",".join(["%s"] * len(PARTS_TO_REPROCESS))
    query = f"""
    SELECT id, url_original, low_poly_url, bbox
    FROM blocks
    WHERE id IN ({placeholders})
    """

    cursor.execute(query, PARTS_TO_REPROCESS)
    rows = cursor.fetchall()

    if len(rows) != len(PARTS_TO_REPROCESS):
        print(f"⚠️  ADVERTENCIA: Solo se encontraron {len(rows)}/{len(PARTS_TO_REPROCESS)} piezas en DB")
        found_ids = {row[0] for row in rows}
        missing_ids = set(PARTS_TO_REPROCESS) - found_ids
        print(f"   IDs faltantes: {', '.join(id[:8] for id in missing_ids)}")

    # Validar que tengan url_original
    valid_parts = {}
    invalid_parts = []

    for row in rows:
        block_id, url_original, low_poly_url, bbox = row
        if not url_original:
            invalid_parts.append(block_id)
        else:
            valid_parts[block_id] = url_original
            status = "✅" if low_poly_url and not bbox else "⚠️ "
            print(f"   {block_id[:8]}: url_original={url_original[:40]}... "
                  f"low_poly_url={'✓' if low_poly_url else '✗'} bbox={'✓' if bbox else '✗'} {status}")

    if invalid_parts:
        print(f"\n❌ ERROR: {len(invalid_parts)} piezas sin url_original:")
        for block_id in invalid_parts:
            print(f"   - {block_id}")
        print("   No se puede reprocesar sin archivo original.")
        sys.exit(1)

    return valid_parts


def reset_low_poly_url(cursor, block_ids):
    """
    Pone low_poly_url = NULL para forzar reprocesamiento

    Args:
        cursor: psycopg2 cursor
        block_ids: list of block UUIDs to reset
    """
    print(f"\n🔄 Reseteando {len(block_ids)} registros (low_poly_url → NULL)...")

    placeholders = ",".join(["%s"] * len(block_ids))
    query = f"""
    UPDATE blocks
    SET low_poly_url = NULL
    WHERE id IN ({placeholders})
    RETURNING id
    """

    cursor.execute(query, block_ids)
    updated_rows = cursor.fetchall()

    print(f"   ✅ {len(updated_rows)} registros actualizados")
    return len(updated_rows)


def enqueue_reprocessing_tasks(broker_url, parts):
    """
    Encola tareas generate_low_poly_glb para cada pieza

    Args:
        broker_url: Redis connection string
        parts: dict {block_id: url_original}

    Returns:
        dict: {block_id: task_id}
    """
    print(f"\n📨 Encolando {len(parts)} tareas Celery...")

    # Crear cliente Celery (solo para enviar tareas, no ejecutar)
    celery_client = Celery("sf-pm-backend", broker=broker_url)
    celery_client.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
    )

    # Nombre de la tarea según agent/constants.py
    TASK_GENERATE_LOW_POLY_GLB = "agent.generate_low_poly_glb"

    task_ids = {}
    for block_id, url_original in parts.items():
        try:
            result = celery_client.send_task(
                TASK_GENERATE_LOW_POLY_GLB,
                args=[block_id]
            )
            task_ids[block_id] = result.id
            print(f"   ✅ {block_id[:8]}: task_id={result.id[:16]}...")
        except Exception as e:
            print(f"   ❌ {block_id[:8]}: Error encolando tarea: {e}")

    return task_ids


def main():
    """Punto de entrada principal"""
    print("=" * 80)
    print("SCRIPT DE REPROCESAMIENTO: DIGITAL TWIN ARCHITECTURE MIGRATION")
    print("=" * 80)
    print("")
    print("Contexto:")
    print("  - Backend ahora guarda bbox absoluto (no centrado)")
    print("  - Backend aplica rotación Z→Y durante export")
    print("  - Frontend posiciona por bbox center (no grid artificial)")
    print("")
    print(f"Piezas a reprocesar: {len(PARTS_TO_REPROCESS)}")
    print("")

    # 1. Cargar configuración
    database_url, broker_url = load_configuration()

    # 2. Conectar a base de datos
    print("🔌 Conectando a PostgreSQL...")
    try:
        conn = psycopg2.connect(database_url)
        cursor = conn.cursor()
        print("   ✅ Conexión establecida")
    except Exception as e:
        print(f"   ❌ Error conectando a DB: {e}")
        sys.exit(1)

    try:
        # 3. Verificar que las piezas existen y tienen url_original
        valid_parts = verify_parts_exist(cursor)

        if not valid_parts:
            print("\n❌ No hay piezas válidas para reprocesar")
            sys.exit(1)

        # 4. Confirmación del usuario
        print(f"\n⚠️  CONFIRMACIÓN REQUERIDA:")
        print(f"   Se van a resetear {len(valid_parts)} registros (low_poly_url → NULL)")
        print(f"   y encolar {len(valid_parts)} tareas de reprocesamiento.")
        print("")
        response = input("   ¿Continuar? (yes/no): ").strip().lower()

        if response not in ["yes", "y", "sí", "si"]:
            print("\n❌ Operación cancelada por el usuario")
            sys.exit(0)

        # 5. Resetear low_poly_url
        block_ids = list(valid_parts.keys())
        updated_count = reset_low_poly_url(cursor, block_ids)

        # 6. Commit cambios DB
        conn.commit()
        print("   ✅ Cambios guardados en DB")

        # 7. Encolar tareas Celery
        task_ids = enqueue_reprocessing_tasks(broker_url, valid_parts)

        # 8. Resumen final
        print("\n" + "=" * 80)
        print("✅ REPROCESAMIENTO INICIADO")
        print("=" * 80)
        print(f"   Registros actualizados: {updated_count}")
        print(f"   Tareas encoladas: {len(task_ids)}")
        print("")
        print("Próximos pasos:")
        print("  1. Verificar que agent-worker está ejecutándose:")
        print("     docker compose ps agent-worker")
        print("")
        print("  2. Monitorear logs del worker:")
        print("     docker compose logs -f agent-worker")
        print("")
        print("  3. Verificar que las piezas tienen bbox después del procesamiento:")
        print("     docker compose exec db psql $DATABASE_URL -c \"SELECT id, bbox IS NOT NULL FROM blocks WHERE id IN (...)\"")
        print("")
        print("  4. Verificar visualización en el canvas:")
        print("     http://localhost:5173 → Dashboard → 3D Canvas")
        print("")

    except Exception as e:
        print(f"\n❌ ERROR durante ejecución: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
