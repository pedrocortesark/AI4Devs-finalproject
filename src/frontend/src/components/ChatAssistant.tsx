/**
 * ChatAssistant — "El Archivista" (US-019, RAG Capa 2)
 *
 * Minimal floating chat panel (bottom-right, fixed overlay so it does not
 * disturb any page layout). Asks POST /api/chat/ask and renders the grounded
 * answer + cited sources. MVP: no streaming, self-contained inline styles.
 */
import { useState, useRef, useEffect } from 'react';
import { askArchivist, type ChatSource } from '../services/chat.service';

interface Turn {
  question: string;
  answer?: string;
  sources?: ChatSource[];
  usedContext?: boolean;
  error?: string;
}

const ACCENT = '#0A84FF';
const BG = '#1C1C1E';
const SURFACE = '#2C2C2E';
const TEXT = '#F2F2F7';
const MUTED = '#8E8E93';

export function ChatAssistant() {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState('');
  const [loading, setLoading] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([]);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [turns, loading]);

  async function send() {
    const question = q.trim();
    if (!question || loading) return;
    setQ('');
    setLoading(true);
    setTurns((t) => [...t, { question }]);
    try {
      const res = await askArchivist(question);
      setTurns((t) => {
        const next = [...t];
        next[next.length - 1] = {
          question,
          answer: res.answer,
          sources: res.sources,
          usedContext: res.used_context,
        };
        return next;
      });
    } catch (e: any) {
      const detail =
        e?.response?.data?.detail ?? e?.message ?? 'Error al consultar al Archivista';
      setTurns((t) => {
        const next = [...t];
        next[next.length - 1] = { question, error: String(detail) };
        return next;
      });
    } finally {
      setLoading(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        aria-label="Abrir El Archivista"
        style={{
          position: 'fixed', right: 20, bottom: 20, zIndex: 1000,
          background: ACCENT, color: '#fff', border: 'none',
          borderRadius: 24, padding: '12px 18px', fontSize: 14, fontWeight: 600,
          cursor: 'pointer', boxShadow: '0 4px 16px rgba(0,0,0,0.35)',
        }}
      >
        💬 El Archivista
      </button>
    );
  }

  return (
    <div
      style={{
        position: 'fixed', right: 20, bottom: 20, zIndex: 1000,
        width: 380, maxWidth: 'calc(100vw - 40px)', height: 520,
        maxHeight: 'calc(100vh - 40px)', display: 'flex', flexDirection: 'column',
        background: BG, color: TEXT, borderRadius: 14,
        border: `1px solid ${SURFACE}`, boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
      }}
    >
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 14px', borderBottom: `1px solid ${SURFACE}`,
      }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700 }}>El Archivista</div>
          <div style={{ fontSize: 11, color: MUTED }}>RAG sobre el inventario</div>
        </div>
        <button
          onClick={() => setOpen(false)}
          aria-label="Cerrar"
          style={{ background: 'none', border: 'none', color: MUTED, fontSize: 18, cursor: 'pointer' }}
        >×</button>
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: 12, display: 'flex', flexDirection: 'column', gap: 12 }}>
        {turns.length === 0 && (
          <div style={{ fontSize: 12, color: MUTED, lineHeight: 1.5 }}>
            Pregunta sobre las piezas del inventario. Ej.: «¿Qué piezas están
            validadas?», «¿Piezas de la agrupación X?». Responde solo con datos
            del inventario.
          </div>
        )}
        {turns.map((t, i) => (
          <div key={i} style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ alignSelf: 'flex-end', background: ACCENT, color: '#fff', padding: '8px 12px', borderRadius: 12, fontSize: 13, maxWidth: '85%' }}>
              {t.question}
            </div>
            {t.answer !== undefined && (
              <div style={{ alignSelf: 'flex-start', background: SURFACE, padding: '8px 12px', borderRadius: 12, fontSize: 13, maxWidth: '90%', whiteSpace: 'pre-wrap' }}>
                {t.answer}
                {t.sources && t.sources.length > 0 && (
                  <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                    {t.sources.map((s) => (
                      <span key={s.block_id} title={`similitud ${s.similarity}`}
                        style={{ fontSize: 10, background: '#3A3A3C', color: MUTED, padding: '2px 6px', borderRadius: 6 }}>
                        {s.iso_code ?? s.block_id.slice(0, 8)}
                      </span>
                    ))}
                  </div>
                )}
                {t.usedContext === false && (
                  <div style={{ marginTop: 6, fontSize: 10, color: MUTED }}>
                    (sin contexto del inventario)
                  </div>
                )}
              </div>
            )}
            {t.error && (
              <div style={{ alignSelf: 'flex-start', background: 'rgba(255,69,58,0.15)', color: '#FF6B60', padding: '8px 12px', borderRadius: 12, fontSize: 12, maxWidth: '90%' }}>
                {t.error}
              </div>
            )}
          </div>
        ))}
        {loading && <div style={{ fontSize: 12, color: MUTED }}>El Archivista está pensando…</div>}
        <div ref={endRef} />
      </div>

      <div style={{ display: 'flex', gap: 8, padding: 12, borderTop: `1px solid ${SURFACE}` }}>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') send(); }}
          placeholder="Pregunta al inventario…"
          disabled={loading}
          style={{
            flex: 1, background: SURFACE, color: TEXT, border: 'none',
            borderRadius: 10, padding: '10px 12px', fontSize: 13, outline: 'none',
          }}
        />
        <button
          onClick={send}
          disabled={loading || !q.trim()}
          style={{
            background: ACCENT, color: '#fff', border: 'none', borderRadius: 10,
            padding: '0 16px', fontSize: 13, fontWeight: 600,
            cursor: loading || !q.trim() ? 'not-allowed' : 'pointer',
            opacity: loading || !q.trim() ? 0.5 : 1,
          }}
        >
          Enviar
        </button>
      </div>
    </div>
  );
}
