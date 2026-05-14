#!/usr/bin/env python3
"""
Monitor de bloques en tiempo real.
Muestra el estado de la tabla blocks cada 3 segundos.
Ctrl+C para salir.
"""
import os, sys, time
sys.path.insert(0, '/app')
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.getenv('SUPABASE_DATABASE_URL')

def check():
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor(cursor_factory=RealDictCursor)

    cur.execute("SELECT COUNT(*) AS total FROM blocks")
    total = cur.fetchone()['total']

    cur.execute("SELECT COUNT(*) AS dupes FROM (SELECT iso_code FROM blocks GROUP BY iso_code HAVING COUNT(*) > 1) t")
    dupes = cur.fetchone()['dupes']

    cur.execute("""
        SELECT iso_code, status, tipologia, created_at::text
        FROM blocks
        ORDER BY created_at DESC
        LIMIT 20
    """)
    rows = cur.fetchall()

    cur.close()
    conn.close()
    return total, dupes, rows

print("=== MONITOR DE BLOQUES (Ctrl+C para salir) ===\n")

prev_total = -1
iteration = 0

try:
    while True:
        total, dupes, rows = check()
        iteration += 1
        ts = time.strftime('%H:%M:%S')

        if total != prev_total:
            delta = f" (+{total - prev_total})" if prev_total >= 0 else ""
            print(f"\n[{ts}] Bloques totales: {total}{delta}  |  iso_codes duplicados: {dupes}")
            if dupes > 0:
                print("  ⚠️  HAY DUPLICADOS DE iso_code — revisar constraint")
            if rows:
                print(f"  Últimos registros (max 20):")
                for r in rows:
                    print(f"    • {r['iso_code']:<40} {r['status']:<20} {r['tipologia']:<20} {r['created_at']}")
            prev_total = total
        else:
            print(f"[{ts}] Sin cambios — {total} bloques", end='\r')

        time.sleep(3)

except KeyboardInterrupt:
    print(f"\n\n=== RESUMEN FINAL ===")
    total, dupes, rows = check()
    print(f"Bloques totales: {total}")
    print(f"iso_codes duplicados: {dupes}")
    if rows:
        for r in rows:
            print(f"  • {r['iso_code']:<40} {r['status']}")
    print("Monitor terminado.")
