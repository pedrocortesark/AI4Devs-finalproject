import psycopg2
from psycopg2.extras import RealDictCursor
import os

conn = psycopg2.connect(os.getenv('SUPABASE_DATABASE_URL'))
cursor = conn.cursor(cursor_factory=RealDictCursor)

cursor.execute("SELECT iso_code, bbox, low_poly_url FROM blocks ORDER BY created_at DESC LIMIT 6")
parts = cursor.fetchall()

print(f"\n{'='*80}")
print(f"PARTS IN DATABASE: {len(parts)}")
print(f"{'='*80}\n")

for p in parts:
    bbox = p['bbox']
    print(f"{p['iso_code']}:")
    if bbox:
        print(f"  min={bbox['min']}")
        print(f"  max={bbox['max']}")
        center = [(bbox['min'][i] + bbox['max'][i])/2 for i in range(3)]
        print(f"  center={[round(c, 2) for c in center]}")
        print(f"  size={[round(bbox['max'][i] - bbox['min'][i], 3) for i in range(3)]}")
    print()

cursor.close()
conn.close()
