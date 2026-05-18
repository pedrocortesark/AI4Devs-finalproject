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


# Curated rhino_metadata UserStrings to embed, ordered with the
# DISCRIMINATING fields first (material, dimensions, volume, weight,
# location/agrupación) so near-identical pieces still get distinct vectors.
# Admin/identical boilerplate (Plano, Arquitecto, Dibujado por, Fecha,
# Cantidad, Fase de proyecto, Tipo de objeto) is dropped — it is the same
# across every piece and only dilutes semantic search. Path/ID noise
# (folders, Guid, CodiArxiu, Prefix) was already excluded. NOTE: the LLM
# tipologia (validation_report.classification) is intentionally NOT embedded:
# it guesses "capitel" from volume and is wrong for this domain — the real
# element type is SF_GEN_NomElement (e.g. "COS" = Costella).
RM_FIELDS = [
    ("Material", "Material"),
    ("SF_GEN_Material", "Material (código)"),
    ("SF_GEN_NomElement", "Elemento"),
    ("SF_GEN_NomSubElement", "Subelemento"),
    ("SF_ARC_PeçaTipus", "Tipo de pieza"),
    ("SF_GEN_Volum_m3", "Volumen (m³)"),
    ("SF_GEN_VolumBrut_m3", "Volumen bruto (m³)"),
    ("SF_GEN_Pes_t", "Peso (t)"),
    ("SF_GEN_AlçadaBruta_m", "Altura bruta (m)"),
    ("SF_GEN_AmpladaBruta_m", "Anchura bruta (m)"),
    ("SF_GEN_ProfunditatBruta_m", "Profundidad bruta (m)"),
    ("SF_GEN_GrauEstructural", "Grado estructural"),
    ("Resistencia", "Resistencia"),
    ("SF_ARC_Agrupacio1", "Agrupación"),
    ("SF_ARC_Agrupacio1Tipus", "Tipo de agrupación"),
    ("SF_LOC_Zona", "Zona"),
    ("SF_LOC_Eix", "Eje"),
    ("SF_PRO_Tram", "Tramo"),
    ("SF_ARC_Filada", "Filada"),
    ("SF_ARC_Numeral", "Numeral"),
]

_EMPTY_SENTINELS = {"", "unknown", "desconocido", "none", "null", "nan", "n/a", "-"}


def _clean(v) -> str | None:
    """Trimmed string, or None if empty / a not-a-value sentinel."""
    if v is None:
        return None
    s = str(v).strip()
    return None if s.lower() in _EMPTY_SENTINELS else s


def _validation_summary(block: dict) -> str:
    status = block.get("status")
    if status == "validated":
        return "Validada correctamente por el Bibliotecario (sin errores)."
    vr = block.get("validation_report") or {}
    errs = vr.get("errors") or []
    if errs:
        parts = [f"{e.get('category', 'error')}: {e.get('message', '')}" for e in errs[:3]]
        return "Rechazada. Motivo(s): " + " | ".join(parts)
    return f"Estado de validación: {status}."


def build_content(block: dict) -> str:
    """NL summary that gets embedded, built from the real SF UserStrings in
    rhino_metadata (authoritative), plus DB status + validation outcome.
    Excludes the unreliable LLM tipologia and filesystem/ID noise."""
    rm = block.get("rhino_metadata")
    if not isinstance(rm, dict):
        rm = {}
    codi = _clean(rm.get("Codi")) or block.get("iso_code") or "desconocida"
    parts = []
    for key, label in RM_FIELDS:
        val = _clean(rm.get(key))
        if val:
            parts.append(f"{label}: {val}")
    body = (". ".join(parts) + ". ") if parts else ""
    return (
        f"Pieza {codi}. {body}"
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
