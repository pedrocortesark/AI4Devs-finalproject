/**
 * Chat service — RAG "The Archivist" (US-019, Capa 2)
 *
 * Calls POST /api/chat/ask: a natural-language question grounded in the
 * block inventory (pgvector semantic search + GPT-4, no hallucination).
 */
import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface ChatSource {
  block_id: string;
  iso_code: string | null;
  similarity: number;
}

export interface ChatAskResponse {
  answer: string;
  sources: ChatSource[];
  used_context: boolean;
}

/**
 * Ask "The Archivist" a question about the inventory.
 * @param question Natural-language question (Spanish)
 * @param topK Number of inventory pieces to retrieve as context
 */
export async function askArchivist(
  question: string,
  topK = 6,
): Promise<ChatAskResponse> {
  const res = await axios.post<ChatAskResponse>(
    `${API_BASE_URL}/api/chat/ask`,
    { question, top_k: topK },
    { headers: { 'Content-Type': 'application/json' }, timeout: 60000 },
  );
  return res.data;
}
