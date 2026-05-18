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


@router.post("/ask", response_model=ChatAskResponse)
@limiter.limit("15/minute")
async def ask(request: Request, body: ChatAskRequest) -> ChatAskResponse:
    """Answer a natural-language question grounded in the block inventory."""
    if not os.environ.get("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY no configurada")

    db_url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DATABASE_URL")
    if not db_url:
        raise HTTPException(status_code=500, detail="DATABASE_URL no configurada")

    client = OpenAI()

    # 1. Embed the question
    try:
        emb = client.embeddings.create(model=EMBED_MODEL, input=[body.question])
        qvec = _vec_literal(emb.data[0].embedding)
    except OpenAIError as e:
        logger.error("chat.embed_failed", error=str(e))
        raise HTTPException(status_code=502, detail=f"Error generando embedding: {e}")

    # Candidate iso_codes mentioned in the question (e.g. GLPER.A-PAE0720.0103).
    # Tokens with >=2 separators; validated against the DB so a permissive
    # regex cannot inject false context (only real blocks match).
    code_candidates = list({
        t.upper()
        for t in re.findall(r"[A-Za-z][A-Za-z0-9]*(?:[.\-][A-Za-z0-9]+){2,}", body.question)
    })

    # 2. Direct iso_code hits (deterministic) + vector search, merged.
    try:
        conn = psycopg2.connect(db_url)
        try:
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

            direct: list = []
            if code_candidates:
                cur.execute(
                    "SELECT b.id AS block_id, be.content, 1.0::float AS similarity "
                    "FROM blocks b JOIN block_embeddings be ON be.block_id = b.id "
                    "WHERE upper(b.iso_code) = ANY(%s)",
                    (code_candidates,),
                )
                direct = cur.fetchall()

            cur.execute(
                "SELECT block_id, content, similarity "
                "FROM match_blocks(%s::vector, %s)",
                (qvec, body.top_k),
            )
            vec = cur.fetchall()

            # Merge: exact iso_code hits first, then vector hits not already in.
            seen = {str(r["block_id"]) for r in direct}
            matches = direct + [v for v in vec if str(v["block_id"]) not in seen]

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
