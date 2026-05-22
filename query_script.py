import psycopg2
import sys
import os
from pathlib import Path


def _load_supabase_url() -> str:
    # 1) Prefer exported environment variables.
    env_url = os.getenv("SUPABASE_DATABASE_URL") or os.getenv("DATABASE_URL")
    if env_url:
        return env_url

    # 2) Fallback: read from local .env in repo root (if present).
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "SUPABASE_DATABASE_URL":
                return value.strip().strip('"').strip("'")

    raise RuntimeError("SUPABASE_DATABASE_URL not found in environment or .env")


connection_url = _load_supabase_url()

try:
    conn = psycopg2.connect(connection_url)
    cur = conn.cursor()
    
    # 1. Count montjuic con patrones material
    # Patterns: %montjuic%, %montjuïc%, %montju%
    # Material columns are Material/SF_GEN_Material according to request
    # Since I don't know the exact column names, I'll first fetch column names from 'pieces' (guessing table name) 
    # or look for tables if piece is wrong.
    
    # Let's find the correct table name first.
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
    tables = cur.fetchall()
    print("Tables:", tables)
    
    # Probably 'pieces' or 'stone_pieces' or similar. 
    # Based on the prompt, it mentions SF_GEN_Material and SF_GEN_Volum_m3.
    
    # I will assume there is a table called 'pieces' or similar.
    # Let's look for a table that has 'SF_GEN_Volum_m3' column.
    cur.execute("""
        SELECT table_name 
        FROM information_schema.columns 
        WHERE column_name = 'SF_GEN_Volum_m3' OR column_name = 'sf_gen_volum_m3'
    """)
    target_tables = cur.fetchall()
    print("Target tables:", target_tables)
    
    if not target_tables:
        print("Could not find table with SF_GEN_Volum_m3")
        sys.exit(1)
        
    table_name = target_tables[0][0]
    
    # Now check for material columns
    cur.execute(f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}'")
    columns = [row[0] for row in cur.fetchall()]
    print("Columns in", table_name, ":", columns)
    
    # Determine the actual column names (handling case sensitivity if they were quoted)
    material_col = next((c for c in columns if c.lower() == 'sf_gen_material'), None)
    volume_col = next((c for c in columns if c.lower() == 'sf_gen_volum_m3'), None)
    
    if not material_col or not volume_col:
        print(f"Required columns not found in {table_name}")
        sys.exit(1)

    # count montjuic
    # patrones: %montjuic%, %montjuïc%, %montju%
    cur.execute(f"""
        SELECT COUNT(*) 
        FROM {table_name} 
        WHERE "{material_col}" ILIKE '%montjuic%' 
           OR "{material_col}" ILIKE '%montjuïc%' 
           OR "{material_col}" ILIKE '%montju%'
    """)
    count_montjuic = cur.fetchone()[0]
    
    # count blavozy
    cur.execute(f"""
        SELECT COUNT(*) 
        FROM {table_name} 
        WHERE "{material_col}" ILIKE '%blavozy%'
    """)
    count_blavozy = cur.fetchone()[0]
    
    # sumatorio SF_GEN_Volum_m3 para blavozy
    cur.execute(f"""
        SELECT SUM("{volume_col}") 
        FROM {table_name} 
        WHERE "{material_col}" ILIKE '%blavozy%'
    """)
    sum_vol_blavozy = cur.fetchone()[0]
    
    print(f"MONTJUIC_COUNT: {count_montjuic}")
    print(f"BLAVOZY_COUNT: {count_blavozy}")
    print(f"BLAVOZY_VOL_SUM: {sum_vol_blavozy}")

    cur.close()
    conn.close()

except Exception as e:
    print("Error:", e)
    sys.exit(1)
