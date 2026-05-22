"""
RAG Chat endpoint — "The Archivist" (US-019, Capa 2)

POST /api/chat/ask
  question → embed (text-embedding-3-small) → match_blocks() cosine search
  → GPT-4 with a strict no-hallucination prompt → answer + cited sources.

MVP scope: schemas are defined here (self-contained); psycopg2 is used for
the vector search (reliable ::vector casting, consistent with
infra/generate_embeddings.py); the OpenAI SDK is used for embeddings + chat.
"""

import os
import re
import unicodedata

import psycopg2
import psycopg2.extras
import structlog
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address
from openai import OpenAI, OpenAIError

logger = structlog.get_logger()
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

EMBED_MODEL = "text-embedding-3-small"          # must match the vector(1536) column
CHAT_MODEL = os.environ.get("RAG_CHAT_MODEL", "gpt-4-turbo")

SYSTEM_PROMPT = (
    "Eres «El Archivista», asistente del inventario de piezas de la Sagrada "
    "Família. Responde ÚNICAMENTE con la información del CONTEXTO. Si la "
    "respuesta no está en el contexto, responde exactamente: «No tengo esa "
    "información en el inventario.» No inventes datos. Cita las piezas por su "
    "iso_code. Responde en español, de forma concisa."
)


class ChatAskRequest(BaseModel):
    question: str = Field(..., min_length=3, description="Pregunta en lenguaje natural")
    top_k: int = Field(5, ge=1, le=20, description="Nº de piezas de contexto a recuperar")


class ChatSource(BaseModel):
    block_id: str
    iso_code: str | None = None
    similarity: float


class ChatAskResponse(BaseModel):
    answer: str
    sources: list[ChatSource]
    used_context: bool = Field(..., description="True si se usó contexto del inventario")


def _vec_literal(values) -> str:
    return "[" + ",".join(repr(float(v)) for v in values) + "]"


def _normalize_text(value: str) -> str:
    """Lowercase + accent-insensitive text for lightweight intent parsing."""
    no_accents = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return no_accents.lower()


def _extract_tram_filters(question: str) -> list[str]:
    """Extract tramo references and normalize to DB format (zero-padded).

    Examples:
    - "tramo 1"  -> ["01"]
    - "tramo 01" -> ["01"]
    - "tramo 2"  -> ["02"]
    """
    trams: set[str] = set()
    for m in re.finditer(r"\btramo\s*0*(\d{1,2})\b", question, flags=re.IGNORECASE):
        n = int(m.group(1))
        if 0 <= n <= 99:
            trams.add(f"{n:02d}")
    return sorted(trams)


def _extract_material_terms(question: str) -> list[str]:
    """Extract known material keywords from a natural-language question."""
    q = _normalize_text(question)
    found: list[str] = []
    for term in ("oro", "marmol", "piedra", "montjuic", "blavozy"):
        if re.search(rf"\b{term}\b", q):
            found.append(term)
    return found


def _material_patterns(term: str) -> list[str]:
    """Return SQL ILIKE patterns for a material term."""
    if term == "oro":
        return ["%oro%", "%dorado%", "%gold%"]
    if term == "marmol":
        return ["%marmol%", "%marbre%", "%mármol%"]
    if term == "piedra":
        return ["%piedra%", "%pedra%", "%m_pedra%"]
    if term == "montjuic":
        return ["%montjuic%", "%montjuïc%", "%montju%"]
    if term == "blavozy":
        return ["%blavozy%"]
    return [f"%{term}%"]


def _is_time_question(question: str) -> bool:
    """Detect out-of-scope time-of-day questions for clearer UX."""
    q = _normalize_text(question)
    return bool(re.search(r"\b(que hora es|hora actual|hora tienes|what time)\b", q))


def _is_workshop_question(question: str) -> bool:
    """Detect questions about workshop assignment."""
    q = _normalize_text(question)
    return "taller" in q


def _is_validated_question(question: str) -> bool:
    """Detect questions about validated pieces."""
    q = _normalize_text(question)
    return "validad" in q and "pieza" in q


def _is_panel_question(question: str) -> bool:
    """Detect questions about panel count/presence."""
    q = _normalize_text(question)
    return "panel" in q or "panell" in q


def _is_volume_sum_question(question: str) -> bool:
    """Detect aggregate volume questions."""
    q = _normalize_text(question)
    has_sum = any(k in q for k in ("sumatorio", "suma", "sumatorio", "total"))
    return has_sum and "volumen" in q


def _is_total_inventory_question(question: str) -> bool:
    """Detect questions asking the total number of pieces in the model/inventory."""
    q = _normalize_text(question)
    has_how_many = any(k in q for k in ("cuantas", "cuantos", "cuanta", "numero de"))
    has_piece_scope = (
        "pieza" in q
        or "inventario" in q
        or "en todo el modelo" in q
        or "todo el modelo" in q
        or "en el modelo" in q
    )
    has_total_scope = (
        "total" in q
        or "en todo" in q
        or "tenemos" in q
        or "hay" in q
    )
    return has_how_many and has_piece_scope and has_total_scope


@router.post("/ask", response_model=ChatAskResponse)
@limiter.limit("15/minute")
async def ask(request: Request, body: ChatAskRequest) -> ChatAskResponse:
    """Answer a natural-language question grounded in the block inventory."""
    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL no configurada")

    client = OpenAI()

    # Out-of-scope fast path: keep UX explicit instead of generic no-context fallback.
    if _is_time_question(body.question):
        return ChatAskResponse(
            answer=(
                "Solo puedo responder sobre el inventario de piezas. "
                "Para la hora actual, consulta el reloj del sistema."
            ),
            sources=[],
            used_context=False,
        )

    # Candidate iso_codes mentioned in the question (e.g. GLPER.A-PAE0720.0103).
    # Tokens with >=2 separators; validated against the DB so a permissive
    # regex cannot inject false context (only real blocks match).
    code_candidates = list({
        t.upper()
        for t in re.findall(r"[A-Za-z][A-Za-z0-9]*(?:[.\-][A-Za-z0-9]+){2,}", body.question)
    })

    # Deterministic filters detected in the question.
    tram_filters = _extract_tram_filters(body.question)
    material_terms = _extract_material_terms(body.question)

    # 1) Deterministic inventory intents (counts/aggregates) +
    # 2) semantic retrieval fallback when needed.
    try:
        conn = psycopg2.connect(db_url)
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            # Total inventory count questions
            if _is_total_inventory_question(body.question):
                cur.execute("SELECT COUNT(*)::int AS total FROM blocks")
                total = int((cur.fetchone() or {"total": 0}).get("total") or 0)
                return ChatAskResponse(
                    answer=f"En el inventario hay {total} piezas.",
                    sources=[],
                    used_context=True,
                )

            # Workshop assignment questions
            if _is_workshop_question(body.question):
                # Current schema may not have a dedicated workshop_id column, so
                # infer assignment from known workshop-related metadata keys.
                cur.execute(
                    "SELECT "
                    "COUNT(*) FILTER (WHERE "
                    "  COALESCE(b.rhino_metadata->>'Taller', '') <> '' OR "
                    "  COALESCE(b.rhino_metadata->>'SF_PRO_Taller', '') <> '' OR "
                    "  COALESCE(b.rhino_metadata->>'Workshop', '') <> ''" 
                    ")::int AS assigned, "
                    "COUNT(*) FILTER (WHERE "
                    "  COALESCE(b.rhino_metadata->>'Taller', '') = '' AND "
                    "  COALESCE(b.rhino_metadata->>'SF_PRO_Taller', '') = '' AND "
                    "  COALESCE(b.rhino_metadata->>'Workshop', '') = ''" 
                    ")::int AS unassigned, "
                    "COUNT(*) FILTER (WHERE "
                    "  b.rhino_metadata ? 'Taller' OR "
                    "  b.rhino_metadata ? 'SF_PRO_Taller' OR "
                    "  b.rhino_metadata ? 'Workshop'" 
                    ")::int AS rows_with_workshop_key "
                    "FROM blocks b"
                )
                row = cur.fetchone() or {
                    "assigned": 0,
                    "unassigned": 0,
                    "rows_with_workshop_key": 0,
                }
                assigned = int(row.get("assigned") or 0)
                unassigned = int(row.get("unassigned") or 0)
                rows_with_key = int(row.get("rows_with_workshop_key") or 0)
                qn = _normalize_text(body.question)

                if rows_with_key == 0:
                    return ChatAskResponse(
                        answer=(
                            "El inventario actual no incluye datos de taller asignado "
                            "para las piezas."
                        ),
                        sources=[],
                        used_context=True,
                    )

                if "sin asign" in qn:
                    return ChatAskResponse(
                        answer=(
                            f"Hay {unassigned} piezas sin taller asignado. "
                            f"Con taller asignado hay {assigned}."
                        ),
                        sources=[],
                        used_context=True,
                    )
                if "asign" in qn:
                    if assigned > 0:
                        return ChatAskResponse(
                            answer=(
                                f"Sí, hay {assigned} piezas con taller asignado. "
                                f"Sin asignar: {unassigned}."
                            ),
                            sources=[],
                            used_context=True,
                        )
                    return ChatAskResponse(
                        answer=(
                            "No, actualmente no hay piezas con taller asignado en el inventario."
                        ),
                        sources=[],
                        used_context=True,
                    )

            # Validated pieces questions (deterministic over full inventory)
            if _is_validated_question(body.question):
                cur.execute(
                    "SELECT COUNT(*)::int AS total FROM blocks WHERE status = 'validated'"
                )
                total = int((cur.fetchone() or {"total": 0}).get("total") or 0)
                cur.execute(
                    "SELECT id AS block_id, iso_code FROM blocks "
                    "WHERE status = 'validated' ORDER BY iso_code LIMIT %s",
                    (max(body.top_k, 6),),
                )
                rows = cur.fetchall()
                sources = [
                    ChatSource(
                        block_id=str(r["block_id"]),
                        iso_code=r.get("iso_code"),
                        similarity=1.0,
                    )
                    for r in rows
                ]
                sample_codes = [s.iso_code for s in sources if s.iso_code][:6]
                sample_text = f" Ejemplos: {', '.join(sample_codes)}." if sample_codes else ""
                return ChatAskResponse(
                    answer=f"Hay {total} piezas validadas en el inventario.{sample_text}",
                    sources=sources,
                    used_context=True,
                )

            # Panel count questions
            if _is_panel_question(body.question):
                cur.execute(
                    "SELECT COUNT(*)::int AS total "
                    "FROM blocks b "
                    "WHERE "
                    "  COALESCE(b.rhino_metadata->>'SF_GEN_NomElement', '') ILIKE '%panel%' OR "
                    "  COALESCE(b.rhino_metadata->>'SF_GEN_NomElement', '') ILIKE '%panell%' OR "
                    "  COALESCE(b.rhino_metadata->>'SF_GEN_NomSubElement', '') ILIKE '%panel%' OR "
                    "  COALESCE(b.rhino_metadata->>'SF_ARC_PeçaTipus', '') ILIKE '%panel%'"
                )
                total = int((cur.fetchone() or {"total": 0}).get("total") or 0)
                return ChatAskResponse(
                    answer=f"En el inventario actual hay {total} paneles.",
                    sources=[],
                    used_context=True,
                )

            # Volume sum by material questions (full inventory, no top_k truncation)
            if _is_volume_sum_question(body.question) and material_terms:
                patterns: list[str] = []
                for t in material_terms:
                    patterns.extend(_material_patterns(t))
                cur.execute(
                    "SELECT "
                    "  COUNT(*)::int AS piece_count, "
                    "  COALESCE(SUM(NULLIF(regexp_replace(COALESCE(b.rhino_metadata->>'SF_GEN_Volum_m3', ''), '[^0-9.\-]', '', 'g'), '')::double precision), 0)::double precision AS total_volume "
                    "FROM blocks b "
                    "WHERE EXISTS ("
                    "  SELECT 1 FROM unnest(%s::text[]) p(pattern) "
                    "  WHERE COALESCE(b.rhino_metadata->>'Material', '') ILIKE p.pattern "
                    "     OR COALESCE(b.rhino_metadata->>'SF_GEN_Material', '') ILIKE p.pattern"
                    ")",
                    (patterns,),
                )
                row = cur.fetchone() or {"piece_count": 0, "total_volume": 0.0}
                piece_count = int(row.get("piece_count") or 0)
                total_volume = float(row.get("total_volume") or 0.0)
                human_terms = " o ".join(material_terms)
                return ChatAskResponse(
                    answer=(
                        f"El sumatorio de volúmenes para {human_terms} es "
                        f"{total_volume:.6f} m³ en {piece_count} piezas."
                    ),
                    sources=[],
                    used_context=True,
                )

            # Material presence/count questions over full inventory.
            if material_terms:
                patterns: list[str] = []
                for t in material_terms:
                    patterns.extend(_material_patterns(t))
                cur.execute(
                    "SELECT COUNT(*)::int AS total "
                    "FROM blocks b "
                    "WHERE EXISTS ("
                    "  SELECT 1 FROM unnest(%s::text[]) p(pattern) "
                    "  WHERE COALESCE(b.rhino_metadata->>'Material', '') ILIKE p.pattern "
                    "     OR COALESCE(b.rhino_metadata->>'SF_GEN_Material', '') ILIKE p.pattern"
                    ")",
                    (patterns,),
                )
                total = int((cur.fetchone() or {"total": 0}).get("total") or 0)
                human_terms = " o ".join(material_terms)

                if total == 0:
                    return ChatAskResponse(
                        answer=f"No hay piezas con material {human_terms} en el inventario actual.",
                        sources=[],
                        used_context=True,
                    )

                cur.execute(
                    "SELECT id AS block_id, iso_code "
                    "FROM blocks b "
                    "WHERE EXISTS ("
                    "  SELECT 1 FROM unnest(%s::text[]) p(pattern) "
                    "  WHERE COALESCE(b.rhino_metadata->>'Material', '') ILIKE p.pattern "
                    "     OR COALESCE(b.rhino_metadata->>'SF_GEN_Material', '') ILIKE p.pattern"
                    ") "
                    "ORDER BY iso_code LIMIT %s",
                    (patterns, max(body.top_k, 6)),
                )
                rows = cur.fetchall()
                sources = [
                    ChatSource(
                        block_id=str(r["block_id"]),
                        iso_code=r.get("iso_code"),
                        similarity=1.0,
                    )
                    for r in rows
                ]
                sample_codes = [s.iso_code for s in sources if s.iso_code][:6]
                sample_text = f" Ejemplos: {', '.join(sample_codes)}." if sample_codes else ""
                return ChatAskResponse(
                    answer=(
                        f"Hay {total} piezas con material {human_terms} en el inventario."
                        f"{sample_text}"
                    ),
                    sources=sources,
                    used_context=True,
                )

            if not os.environ.get("OPENAI_API_KEY"):
                raise HTTPException(status_code=503, detail="OPENAI_API_KEY no configurada")

            # 2. Embed the question for semantic fallback
            try:
                emb = client.embeddings.create(model=EMBED_MODEL, input=[body.question])
                qvec = _vec_literal(emb.data[0].embedding)
            except OpenAIError as e:
                logger.error("chat.embed_failed", error=str(e))
                raise HTTPException(status_code=502, detail=f"Error generando embedding: {e}")

            direct: list = []
            if code_candidates:
                cur.execute(
                    "SELECT b.id AS block_id, be.content, 1.0::float AS similarity "
                    "FROM blocks b JOIN block_embeddings be ON be.block_id = b.id "
                    "WHERE upper(b.iso_code) = ANY(%s)",
                    (code_candidates,),
                )
                direct = cur.fetchall()

            material_direct: list = []
            if material_terms:
                # Expand requested material terms into ILIKE patterns and retrieve
                # deterministic candidates from metadata-backed fields.
                patterns: list[str] = []
                for t in material_terms:
                    patterns.extend(_material_patterns(t))

                cur.execute(
                    "SELECT b.id AS block_id, be.content, 0.98::float AS similarity "
                    "FROM blocks b "
                    "JOIN block_embeddings be ON be.block_id = b.id "
                    "WHERE EXISTS ("
                    "  SELECT 1 FROM unnest(%s::text[]) p(pattern) "
                    "  WHERE COALESCE(b.rhino_metadata->>'Material', '') ILIKE p.pattern "
                    "     OR COALESCE(b.rhino_metadata->>'SF_GEN_Material', '') ILIKE p.pattern"
                    ")",
                    (patterns,),
                )
                material_direct = cur.fetchall()

            # Tramo-aware deterministic retrieval: avoids semantic misses for
            # questions like "tramo 1" when DB stores "01"/"02".
            tram_direct: list = []
            if tram_filters:
                cur.execute(
                    "SELECT b.id AS block_id, be.content, 0.99::float AS similarity "
                    "FROM blocks b "
                    "JOIN block_embeddings be ON be.block_id = b.id "
                    "WHERE COALESCE(b.rhino_metadata->>'SF_PRO_Tram', '') = ANY(%s)",
                    (tram_filters,),
                )
                tram_direct = cur.fetchall()

            cur.execute(
                "SELECT block_id, content, similarity "
                "FROM match_blocks(%s::vector, %s)",
                (qvec, body.top_k),
            )
            vec = cur.fetchall()

            # Merge order: exact iso_code hits, then tramo/material hits, then vector
            # hits not already included.
            seen = {str(r["block_id"]) for r in direct}
            merged = list(direct)
            for t in tram_direct:
                tid = str(t["block_id"])
                if tid not in seen:
                    merged.append(t)
                    seen.add(tid)
            for m in material_direct:
                mid = str(m["block_id"])
                if mid not in seen:
                    merged.append(m)
                    seen.add(mid)
            matches = merged + [v for v in vec if str(v["block_id"]) not in seen]

            iso_by_id: dict = {}
            if matches:
                ids = [str(m["block_id"]) for m in matches]
                cur.execute(
                    "SELECT id, iso_code FROM blocks WHERE id = ANY(%s::uuid[])",
                    (ids,),
                )
                iso_by_id = {str(r["id"]): r["iso_code"] for r in cur.fetchall()}
            cur.close()
        finally:
            conn.close()
    except Exception as e:
        logger.exception("chat.match_failed", error=str(e))
        raise HTTPException(status_code=500, detail=f"Error en búsqueda semántica: {e}")

    if not matches:
        return ChatAskResponse(
            answer="No tengo datos en el inventario todavía (no hay embeddings; "
                   "ejecuta el backfill tras la ingesta).",
            sources=[],
            used_context=False,
        )

    # If the user asked for a tramo and we have deterministic hits, return a
    # precise summary without relying on LLM interpretation.
    if tram_filters:
        tramo_human = ", ".join(str(int(t)) for t in tram_filters)
        tramo_hits = [m for m in matches if float(m["similarity"]) >= 0.99]
        if tramo_hits:
            iso_preview = [iso_by_id.get(str(m["block_id"])) for m in tramo_hits]
            iso_preview = [i for i in iso_preview if i][: min(12, len(iso_preview))]
            answer = (
                f"En el tramo {tramo_human} hay {len(tramo_hits)} piezas en el inventario. "
                f"Ejemplos: {', '.join(iso_preview)}."
            )
            sources = [
                ChatSource(
                    block_id=str(m["block_id"]),
                    iso_code=iso_by_id.get(str(m["block_id"])),
                    similarity=round(float(m["similarity"]), 4),
                )
                for m in tramo_hits[: max(body.top_k, 6)]
            ]
            logger.info(
                "chat.ask.tramo_ok",
                q=body.question[:80],
                tramo=tram_filters,
                hits=len(tramo_hits),
            )
            return ChatAskResponse(answer=answer, sources=sources, used_context=True)

    # 3. Build context + ask GPT-4 (grounded, no hallucination)
    context = "\n".join(
        f"{i + 1}. [{iso_by_id.get(str(m['block_id'])) or m['block_id']}] {m['content']}"
        for i, m in enumerate(matches)
    )
    try:
        chat = client.chat.completions.create(
            model=CHAT_MODEL,
            temperature=0,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",
                 "content": f"CONTEXTO (piezas del inventario):\n{context}\n\n"
                            f"PREGUNTA: {body.question}"},
            ],
        )
        answer = (chat.choices[0].message.content or "").strip()
    except OpenAIError as e:
        logger.error("chat.completion_failed", error=str(e))
        raise HTTPException(status_code=502, detail=f"Error consultando el LLM: {e}")

    sources = [
        ChatSource(
            block_id=str(m["block_id"]),
            iso_code=iso_by_id.get(str(m["block_id"])),
            similarity=round(float(m["similarity"]), 4),
        )
        for m in matches
    ]
    logger.info("chat.ask.ok", q=body.question[:80], matches=len(matches), model=CHAT_MODEL)
    return ChatAskResponse(answer=answer, sources=sources, used_context=True)
