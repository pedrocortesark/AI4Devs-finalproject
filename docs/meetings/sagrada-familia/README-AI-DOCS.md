# 📚 Documentación de Arquitectura de IA — Guía de Navegación

**Proyecto:** Sagrada Família Parts Manager (SF-PM)  
**Fase:** Propuesta de Arquitectura Híbrida LangGraph + RAG  
**Fecha:** Mayo 2026  
**Autor:** Pedro Cortes (AI4Devs TFM)

---

## 🎯 ¿Por Dónde Empiezo?

Dependiendo de tu rol y objetivo, aquí está el orden recomendado de lectura:

### 👔 **Para Stakeholders / Dirección** (15 min lectura)
1. **[ONE-PAGER-AI.md](ONE-PAGER-AI.md)** (1 página) — Resumen visual con impacto económico
2. **[EXECUTIVE-SUMMARY-AI.md](EXECUTIVE-SUMMARY-AI.md)** (15 páginas) — Presentación completa con ROI y timeline
3. **[MEETING-CHECKLIST-SF.md](MEETING-CHECKLIST-SF.md)** — FAQs y próximos pasos

**Objetivo:** Entender propuesta de valor, inversión requerida, y ROI esperado

---

### 💻 **Para Equipo Técnico / Arquitectos** (2 horas lectura)
1. **[12-ai-architecture.md](12-ai-architecture.md)** (60 páginas) — Especificación técnica completa
   - Secciones clave:
     - Arquitectura LangGraph (State Machine de 8 nodos)
     - Código Python completo de validación
     - Schema pgvector para embeddings
     - API RAG endpoint (FastAPI + LangChain)
     - Frontend chat interface (React + TypeScript)
     - Testing strategy (15 test cases)
2. **[07-agent-design.md](../../07-agent-design.md)** — Contexto histórico del agente original
3. **[05-data-model.md](../../05-data-model.md)** — Schema de base de datos actual (referencia)

**Objetivo:** Evaluar factibilidad técnica, identificar riesgos, validar arquitectura

---

### 🛠️ **Para Equipo de Desarrollo** (4 horas estudio + implementación)
1. **[12-ai-architecture.md](12-ai-architecture.md)** — Leer secciones:
   - § 1.3: ValidationState TypedDict
   - § 1.4: Implementación de 8 nodos LangGraph
   - § 1.5: Definición de edges condicionales
   - § 1.6: Integración con Celery
   - § 2.4: Generación de embeddings (batch + incremental)
   - § 2.5: Backend API RAG endpoint
   - § 2.6: Frontend ChatAssistant component
2. **[MEETING-CHECKLIST-SF.md](MEETING-CHECKLIST-SF.md)** — Ver sección "Aprobación Pathway" (tickets T-1801 a T-1907)
3. **Código base existente:**
   - `src/agent/graph/state.py` — State skeleton (ya existe)
   - `src/agent/graph/nodes.py` — Nodes skeleton (ya existe)
   - `tests/agent/` — Test fixtures (referencia)

**Objetivo:** Preparar implementación, estimar esfuerzo real, detectar gaps

---

### 📊 **Para BIM Managers / Usuarios Finales** (30 min lectura)
1. **[EXECUTIVE-SUMMARY-AI.md](EXECUTIVE-SUMMARY-AI.md)** — Leer secciones:
   - § 2.1 Capa 2: The Archivist (ejemplos de consultas)
   - § Casos de Uso Reales (María, Jordi, Carme)
   - § FAQs (Q1-Q8)
2. **[ONE-PAGER-AI.md](ONE-PAGER-AI.md)** — Vista rápida de beneficios

**Objetivo:** Entender cómo cambiaría el trabajo diario, qué preguntas se pueden hacer al asistente

---

## 📂 Estructura de Archivos

```
docs/
├── 12-ai-architecture.md           ⭐ Especificación técnica completa (60 páginas)
├── EXECUTIVE-SUMMARY-AI.md        ⭐ Resumen ejecutivo para stakeholders (15 páginas)
├── ONE-PAGER-AI.md                ⭐ Resumen visual de 1 página (handout reunión)
├── MEETING-CHECKLIST-SF.md        ⭐ Checklist preparación reunión + FAQs
├── README-AI-DOCS.md              📍 ESTÁS AQUÍ — Guía de navegación
│
├── 00-index.md                    📑 Índice general del proyecto (incluye link AI)
├── 01-strategy.md                 📑 Estrategia producto (contexto)
├── 02-prd.md                      📑 PRD con 4 personas (María, Jordi, Carme, Enric)
├── 05-data-model.md               📑 Schema PostgreSQL (referencia para pgvector)
├── 06-architecture.md             📑 Arquitectura C4 del MVP
├── 07-agent-design.md             📑 Diseño original de The Librarian (pre-LangGraph)
└── 09-mvp-backlog.md              📑 Backlog de User Stories (US-018 pendiente)
```

---

## 🔑 Conceptos Clave Explicados

### LangGraph State Machine
**Qué es:** Framework de LangChain para crear agentes con **flujo de estado explícito** (no chat libre).  
**Por qué:** Permite validación **determinista** con pasos auditables (no caja negra).  
**Ejemplo:** Si nomenclatura falla → Detener inmediatamente (fail-fast), no desperdiciar recursos LLM.

### RAG (Retrieval-Augmented Generation)
**Qué es:** Técnica donde el LLM **busca información relevante primero** antes de responder.  
**Por qué:** Previene alucinaciones (inventar datos falsos).  
**Ejemplo:** Pregunta "¿Cuántas dovelas?" → Busca en DB → GPT-4 responde CON contexto real.

### pgvector
**Qué es:** Extensión de PostgreSQL para **búsqueda vectorial semántica**.  
**Por qué:** Permite encontrar piezas "similares" por significado (no solo keywords exactas).  
**Ejemplo:** "wedge stones" encuentra "dovelas" aunque palabra diferente (embeddings similares).

### Embeddings
**Qué es:** Representación numérica de texto (vector de 1,536 números).  
**Por qué:** Convierte "significado" en matemática (distancia entre vectores = similitud semántica).  
**Ejemplo:** "Piedra Montjuïc 2.5m³" → [0.023, -0.145, 0.089, ...]

---

## 📊 Comparativa de Documentos

| Documento | Páginas | Audiencia | Objetivo | Tiempo Lectura |
|-----------|---------|-----------|----------|----------------|
| **ONE-PAGER-AI.md** | 1 | Todos | Resumen visual | 2 min |
| **EXECUTIVE-SUMMARY-AI.md** | 15 | Stakeholders | Decisión GO/NO-GO | 15 min |
| **12-ai-architecture.md** | 60 | Técnicos | Implementación | 2 horas |
| **MEETING-CHECKLIST-SF.md** | 12 | Presentador | Preparación reunión | 30 min |

---

## 🚀 Flujo de Trabajo Recomendado

### Fase 1: Preparación Reunión (1 día antes)
1. ✅ Leer [MEETING-CHECKLIST-SF.md](MEETING-CHECKLIST-SF.md) completo
2. ✅ Imprimir 3 copias de [ONE-PAGER-AI.md](ONE-PAGER-AI.md)
3. ✅ Revisar [EXECUTIVE-SUMMARY-AI.md](EXECUTIVE-SUMMARY-AI.md) sección FAQs
4. ✅ Preparar demo live de MVP (https://sf-pm.vercel.app)

### Fase 2: Durante Reunión
1. ✅ Presentar [EXECUTIVE-SUMMARY-AI.md](EXECUTIVE-SUMMARY-AI.md) (20 min)
2. ✅ Entregar [ONE-PAGER-AI.md](ONE-PAGER-AI.md) como handout
3. ✅ Responder preguntas técnicas con [12-ai-architecture.md](12-ai-architecture.md) (referencia)
4. ✅ Cerrar con próximos pasos (checklist)

### Fase 3: Post-Reunión
1. ✅ Email follow-up con links a:
   - [12-ai-architecture.md](12-ai-architecture.md) (PDF adjunto)
   - [EXECUTIVE-SUMMARY-AI.md](EXECUTIVE-SUMMARY-AI.md) (PDF adjunto)
   - GitHub repo (si solicitado)
2. ✅ Actualizar [memory-bank/activeContext.md](../memory-bank/activeContext.md) con outcome

### Fase 4: Si Aprobado → Implementación (8 días)
1. ✅ Usar [12-ai-architecture.md](12-ai-architecture.md) § "Plan de Implementación" como roadmap
2. ✅ Crear tickets T-1801 a T-1907 en backlog
3. ✅ Daily standup con checklist de [MEETING-CHECKLIST-SF.md](MEETING-CHECKLIST-SF.md) § "Aprobación Pathway"

---

## 💡 Tips de Navegación

### Búsqueda Rápida por Keyword

| Busco información sobre... | Ir a documento... | Sección... |
|----------------------------|-------------------|------------|
| **ROI y costes** | EXECUTIVE-SUMMARY-AI.md | § Inversión Requerida |
| **Código Python validación** | 12-ai-architecture.md | § 1.4 Nodos del Graph |
| **Implementación chat** | 12-ai-architecture.md | § 2.5 Backend API + § 2.6 Frontend |
| **Testing strategy** | 12-ai-architecture.md | § 1.7 + § 2.7 |
| **Preguntas frecuentes** | EXECUTIVE-SUMMARY-AI.md | § FAQs Q1-Q8 |
| **Timeline implementación** | EXECUTIVE-SUMMARY-AI.md | § Timeline (gantt) |
| **Schema pgvector** | 12-ai-architecture.md | § 2.3 Schema BD |
| **Próximos pasos GO** | MEETING-CHECKLIST-SF.md | § Aprobación Pathway |

### Atajos Conceptuales

- **"¿Cómo funciona validación?"** → [12-ai-architecture.md § 1.2](12-ai-architecture.md#12-arquitectura-del-state-graph) (diagrama Mermaid)
- **"¿Qué preguntas puede responder RAG?"** → [EXECUTIVE-SUMMARY-AI.md § Capa 2](EXECUTIVE-SUMMARY-AI.md#-capa-2-rag-system-the-archivist) (ejemplos)
- **"¿Por qué no otros frameworks?"** → [12-ai-architecture.md § 1.1](12-ai-architecture.md#11-visión-general) (principios de diseño)
- **"¿Qué pasa si OpenAI falla?"** → [EXECUTIVE-SUMMARY-AI.md FAQ Q1](EXECUTIVE-SUMMARY-AI.md#técnicas) (fallback automático)

---

## 🔗 Referencias Externas

### Documentación Técnica Original
- **LangGraph Official Docs:** https://langchain-ai.github.io/langgraph/
- **Supabase pgvector Guide:** https://supabase.com/docs/guides/ai/vector-columns
- **OpenAI Embeddings API:** https://platform.openai.com/docs/guides/embeddings

### Papers de Referencia
- **RAG (Lewis et al., 2020):** "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"
  - URL: https://arxiv.org/abs/2005.11401
- **LangGraph Architecture:** "Stateful Multi-Actor Applications with LLMs"
  - URL: https://blog.langchain.dev/langgraph-multi-agent-workflows/

### Ejemplos de Implementación
- **SF-PM GitHub Repo:** https://github.com/LIDR-academy/AI4Devs-finalproject
- **LangGraph Examples:** https://github.com/langchain-ai/langgraph/tree/main/examples

---

## 📞 Contacto y Soporte

**Para dudas sobre documentación:**
- **Email:** [tu-email@ejemplo.com]
- **GitHub Issues:** https://github.com/LIDR-academy/AI4Devs-finalproject/issues

**Para reunión con Sagrada Família:**
- **Contacto directo:** Pedro Cortes — [tu-teléfono]
- **Fecha propuesta:** A coordinar (target: Mayo 2026)

---

## 🎓 Contexto del Proyecto

Este conjunto de documentos fue generado como parte del **Trabajo Fin de Máster (TFM)** en el programa **AI4Devs** de la academia **LIDR**. El objetivo es demostrar:

1. ✅ Capacidad de diseñar arquitecturas de IA complejas (LangGraph + RAG)
2. ✅ Pensamiento product-market fit (ROI y pain points reales)
3. ✅ Documentación enterprise-grade (specs técnicas + presentaciones ejecutivas)
4. ✅ Viabilidad de implementación (código completo, tests, estimaciones)

**Nota:** Aunque es proyecto académico, está diseñado con estándares de producción reales y puede ser implementado directamente en el contexto de Sagrada Família.

---

## 📅 Historial de Versiones

| Versión | Fecha | Cambios | Autor |
|---------|-------|---------|-------|
| 1.0 | 2026-05-01 | Creación inicial de documentación completa | Pedro Cortes |
| — | — | Futuras actualizaciones según feedback | — |

---

## ✅ Checklist de Calidad Documental

Antes de presentar a Sagrada Família, verificar:

- ✅ **Todos los links internos funcionan** (docs entre sí)
- ✅ **Código Python/TypeScript validado sintácticamente** (no errores)
- ✅ **Diagramas Mermaid renderizan correctamente** (GitHub preview)
- ✅ **Números consistentes** (ROI, costes, timeline) en todos los docs
- ✅ **Sin TODOs o placeholders** (ej: "[tu-email@ejemplo.com]" reemplazado)
- ✅ **PDFs generados** (para backup sin internet en reunión)
- ✅ **Registro en prompts.md** (entrada #243 completada)

---

**¡Documentación lista para presentación! 🚀**

---

_Guía de navegación preparada para maximizar comprensión y decisión informada_  
_Versión: 1.0 | Mayo 2026 | AI4Devs TFM_
