"""
Generate Block Embeddings — RAG ("The Archivist") backfill — US-019

Builds a short natural-language summary per block and stores its
text-embedding-3-small (1536-d) vector in block_embeddings (upsert by
block_id) so POST /api/chat/ask can do semantic search via match_blocks().

Usage (inside Docker, fresh container so it reads the current .env):
    docker compose run --rm backend python /app/infra/generate_embeddings.py
    docker compose run --rm backend python /app/infra/generate_embeddings.py --dry-run
    docker compose run --rm backend python /app/infra/generate_embeddings.py --limit 50

Notes:
- psycopg2 is used for DB I/O (PostgREST does not cleanly cast JSON arrays
  to pgvector); OpenAI SDK for embeddings.
- Idempotent: ON CONFLICT (block_id) updates content/embedding/updated_at.
- Safe on an empty DB: reports "0 blocks" and exits 0.
"""

import argparse
import os
import sys

import psycopg2
import psycopg2.extras
from openai import OpenAI

EMBED_MODEL = "text-embedding-3-small"   # 1536 dims → matches vector(1536)
EMBED_DIMS = 1536
BATCH_SIZE = 96                          # OpenAI accepts batched inputs


def _material(block: dict) -> str:
    """Material from validation_report classification, falling back to the
    rhino_metadata 'Material' UserString (flat / nested document / objects)."""
    vr = block.get("validation_report") or {}
    cl = (vr.get("metadata") or {}).get("classification") or {}
    if cl.get("material"):
        return str(cl["material"])
    rm = block.get("rhino_metadata") or {}
    if isinstance(rm, dict):
        if rm.get("Material"):
            return str(rm["Material"])
        doc = rm.get("document")
        if isinstance(doc, dict) and doc.get("Material"):
            return str(doc["Material"])
        objs = rm.get("objects")
        if isinstance(objs, dict):
            for v in objs.values():
                if isinstance(v, dict) and v.get("Material"):
                    return str(v["Material"])
    return "desconocido"


def _agrupacio(block: dict) -> str:
    rm = block.get("rhino_metadata") or {}
    val = rm.get("SF_ARC_Agrupacio1") if isinstance(rm, dict) else None
    return str(val) if val else "sin agrupación"


def _validation_summary(block: dict) -> str:
    status = block.get("status")
    if status == "validated":
        return "Validada correctamente por el Bibliotecario (sin errores)."
    vr = block.get("validation_report") or {}
    errs = vr.get("errors") or []
    if errs:
        parts = [f"{e.get('category', 'error')}: {e.get('message', '')}" for e in errs[:3]]
        return f"Rechazada. Motivo(s): " + " | ".join(parts)
    return f"Estado de validación: {status}."


def build_content(block: dict) -> str:
    """Compact NL summary that gets embedded. Optimised for questions about
    typology, material, status/rejections and architectural grouping."""
    return (
        f"Pieza {block.get('iso_code')}. "
        f"Tipología: {block.get('tipologia') or 'desconocida'}. "
        f"Material: {_material(block)}. "
        f"Agrupación arquitectónica: {_agrupacio(block)}. "
        f"Estado: {block.get('status')}. "
        f"{_validation_summary(block)}"
    )


def _vec_literal(values) -> str:
    """pgvector text input format: '[f1,f2,...]'."""
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


def main() -> int:
    ap = argparse.ArgumentParser(description="Backfill block_embeddings for RAG.")
    ap.add_argument("--limit", type=int, default=None, help="Only process N blocks")
    ap.add_argument("--dry-run", action="store_true", help="Don't write; print samples")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = ap.parse_args()

    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL / SUPABASE_DATABASE_URL not set", file=sys.stderr)
        return 2
    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set (restart container after editing .env)", file=sys.stderr)
        return 2

    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    q = ("SELECT id, iso_code, status, tipologia, rhino_metadata, validation_report "
         "FROM blocks ORDER BY created_at")
    if args.limit:
        q += f" LIMIT {int(args.limit)}"
    cur.execute(q)
    blocks = cur.fetchall()

    if not blocks:
        print("0 blocks in DB — nothing to embed.")
        cur.close()
        conn.close()
        return 0

    print(f"Embedding {len(blocks)} blocks with {EMBED_MODEL} ...")
    client = OpenAI()
    upserted = 0

    for start in range(0, len(blocks), args.batch_size):
        batch = blocks[start:start + args.batch_size]
        contents = [build_content(b) for b in batch]

        if args.dry_run:
            for b, c in list(zip(batch, contents))[:3]:
                print(f"  [{b['iso_code']}] {c}")
            print(f"  (dry-run) batch {start}-{start + len(batch)} not embedded/written")
            continue

        resp = client.embeddings.create(model=EMBED_MODEL, input=contents)
        rows = [
            (str(b["id"]), c, _vec_literal(resp.data[i].embedding))
            for i, (b, c) in enumerate(zip(batch, contents))
        ]
        psycopg2.extras.execute_values(
            cur,
            # updated_at omitted from the column list (DEFAULT now() on insert);
            # set explicitly only on the conflict/update path.
            "INSERT INTO block_embeddings (block_id, content, embedding) "
            "VALUES %s "
            "ON CONFLICT (block_id) DO UPDATE SET "
            "content = EXCLUDED.content, embedding = EXCLUDED.embedding, updated_at = now()",
            rows,
            template="(%s, %s, %s::vector)",
        )
        conn.commit()
        upserted += len(rows)
        print(f"  upserted {upserted}/{len(blocks)}")

    cur.close()
    conn.close()
    print(f"Done. {'(dry-run, 0 written)' if args.dry_run else f'{upserted} embeddings upserted.'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
