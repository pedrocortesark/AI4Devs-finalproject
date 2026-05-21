"""
embed_block — single-block embedding task for "The Archivist" (RAG layer).

Auto-fired by `validate_file` after a successful validation so a newly-ingested
piece is immediately findable by the chat (`/api/chat/ask`) — no manual backfill
needed for the demo flow.

Mirrors the per-row logic of `infra/generate_embeddings.py` (which remains the
bulk backfill tool). Helper functions (`build_content`, `RM_FIELDS`, etc.) are
duplicated here intentionally: `infra/` is not part of the agent-worker image
and we want this task to be self-contained.

Implementation notes:
- Uses psycopg2 for both SELECT and UPSERT — pgvector ::vector cast doesn't
  round-trip cleanly via PostgREST/Supabase client.
- Idempotent (`ON CONFLICT (block_id) DO UPDATE`).
- Soft-fails: if embedding can't be produced (LLM/DB issue), we log and exit
  cleanly; the bulk backfill script remains the safety net.
- Auto-retry only for clearly transient OpenAI errors (rate limit, 5xx).
"""

import os
from typing import Optional

import psycopg2
import psycopg2.extras
import structlog
from openai import OpenAI

# Conditional imports: src.agent.* preferred (tests + dev), fallback to direct (production)
try:
    from src.agent.celery_app import celery_app
    from src.agent.constants import (
        TASK_EMBED_BLOCK,
        TASK_MAX_RETRIES,
        TASK_RETRY_DELAY_SECONDS,
    )
except ImportError:
    from celery_app import celery_app
    from constants import (
        TASK_EMBED_BLOCK,
        TASK_MAX_RETRIES,
        TASK_RETRY_DELAY_SECONDS,
    )

logger = structlog.get_logger()

EMBED_MODEL = "text-embedding-3-small"  # 1536 dims → matches vector(1536)


# ─── Content builder (duplicated from infra/generate_embeddings.py) ────────────
# Discriminating fields first (material, dimensions, volume, weight, location)
# so near-identical pieces still get distinct vectors. LLM tipologia is excluded
# (validation_report.classification): unreliable for this domain — the real
# element type is SF_GEN_NomElement.
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


def _clean(v) -> Optional[str]:
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


def _build_content(block: dict) -> str:
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


# ─── Transient error detection (mirrors file_validation._is_transient_error) ──
def _is_transient_openai_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(p in msg for p in (
        "rate limit", "timeout", "connection", "503", "502", "504",
        "temporary", "unavailable", "overloaded",
    ))


# ─── Task ──────────────────────────────────────────────────────────────────────
@celery_app.task(
    name=TASK_EMBED_BLOCK,
    bind=True,
    max_retries=3,
    default_retry_delay=TASK_RETRY_DELAY_SECONDS,
)
def embed_block(self, block_id: str):
    """
    Generate and upsert a single block's RAG embedding.

    Reads the block row (rhino_metadata, status, validation_report, iso_code),
    builds a curated NL summary, embeds it with text-embedding-3-small, and
    upserts into `block_embeddings` (ON CONFLICT updates content/embedding).

    Soft-fails on any non-transient error: the bulk backfill remains the safety
    net. Transient OpenAI errors trigger Celery retry with exponential backoff.

    Args:
        block_id: UUID of the row in `blocks`

    Returns:
        dict: {"success": bool, "block_id": str, "skipped": Optional[str]}
    """
    logger.info("embed_block.started", block_id=block_id)

    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DATABASE_URL")
    if not db_url:
        logger.error("embed_block.no_db_url", block_id=block_id)
        return {"success": False, "block_id": block_id, "skipped": "no_db_url"}
    if not os.environ.get("OPENAI_API_KEY"):
        logger.error("embed_block.no_openai_key", block_id=block_id)
        return {"success": False, "block_id": block_id, "skipped": "no_openai_key"}

    conn = None
    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, iso_code, status, tipologia, rhino_metadata, validation_report "
                "FROM blocks WHERE id = %s",
                (block_id,),
            )
            row = cur.fetchone()
            if row is None:
                logger.warning("embed_block.block_not_found", block_id=block_id)
                return {"success": False, "block_id": block_id, "skipped": "not_found"}

            content = _build_content(dict(row))

            try:
                resp = OpenAI().embeddings.create(model=EMBED_MODEL, input=[content])
            except Exception as openai_exc:
                if _is_transient_openai_error(openai_exc):
                    countdown = TASK_RETRY_DELAY_SECONDS * (2 ** self.request.retries)
                    logger.warning(
                        "embed_block.openai_retry",
                        block_id=block_id,
                        retry=self.request.retries + 1,
                        countdown_s=countdown,
                        error=str(openai_exc),
                    )
                    raise self.retry(exc=openai_exc, countdown=countdown)
                logger.exception("embed_block.openai_permanent", block_id=block_id, error=str(openai_exc))
                return {"success": False, "block_id": block_id, "skipped": "openai_error"}

            vec = _vec_literal(resp.data[0].embedding)

            # Upsert (ON CONFLICT updates content + embedding + updated_at)
            cur.execute(
                "INSERT INTO block_embeddings (block_id, content, embedding) "
                "VALUES (%s, %s, %s::vector) "
                "ON CONFLICT (block_id) DO UPDATE SET "
                "content = EXCLUDED.content, embedding = EXCLUDED.embedding, updated_at = now()",
                (str(row["id"]), content, vec),
            )
            conn.commit()

        logger.info("embed_block.success", block_id=block_id, content_chars=len(content))
        return {"success": True, "block_id": block_id, "skipped": None}

    except Exception as e:
        if conn is not None:
            try:
                conn.rollback()
            except Exception:
                pass
        # Don't retry on unexpected exceptions — log and exit cleanly. The
        # bulk backfill script will catch this block next time it runs.
        logger.exception("embed_block.unexpected_error", block_id=block_id, error=str(e))
        return {"success": False, "block_id": block_id, "skipped": "exception"}
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
