# 🏛️ Presentación Sagrada Família — Arquitectura de IA

**Reunión:** Propuesta Comercial Sistema Inteligente SF-PM  
**Fecha objetivo:** Mayo 3-5, 2026  
**Contacto:** Dirección Técnica + BIM Managers Sagrada Família  
**Status:** 📋 Documentación completa — Awaiting GO/NO-GO decision

---

## 📋 Contenido de esta Carpeta

Esta carpeta contiene **6 documentos** preparados para la presentación de propuesta comercial a Sagrada Família sobre la implementación de arquitectura híbrida de IA (LangGraph + RAG) en el sistema SF-PM.

### 📚 Documentación de Presentación

| Archivo | Tipo | Audiencia | Descripción |
|---------|------|-----------|-------------|
| **[README-AI-DOCS.md](README-AI-DOCS.md)** | 📍 Índice | Todos | **START HERE** — Guía de navegación y orden de lectura |
| **[ONE-PAGER-AI.md](ONE-PAGER-AI.md)** | 📄 Handout | Stakeholders | Resumen visual 1 página (imprimir 3 copias) |
| **[EXECUTIVE-SUMMARY-AI.md](EXECUTIVE-SUMMARY-AI.md)** | 📊 Propuesta | Dirección | Presentación 15 páginas con ROI + Timeline |
| **[12-ai-architecture.md](12-ai-architecture.md)** | 🛠️ Spec Técnica | Developers | Especificación completa 60 páginas (código incluido) |
| **[MEETING-CHECKLIST-SF.md](MEETING-CHECKLIST-SF.md)** | ✅ Checklist | Presentador | Preparación reunión + Script + FAQs |
| **[BACKLOG-AI-REVIEW.md](BACKLOG-AI-REVIEW.md)** | 🔍 Análisis Interno | Dev Team | Consistencia backlog (no presentar) |

---

## 🎯 Propuesta en Resumen

**Objetivo:** Transformar SF-PM de MVP funcional a plataforma inteligente enterprise-ready mediante:

1. **The Librarian (LangGraph):** Validación automática pre-ingesta con LLM
   - 98% accuracy en clasificación de tipología
   - Circuit breaker para degradación graceful
   - 10 segundos vs. 3 horas validación manual

2. **The Archivist (RAG System):** Q&A semántica sobre inventario
   - pgvector + OpenAI embeddings (1536D)
   - Respuestas con fuentes citadas
   - 97% reducción tiempo búsqueda (3h → 10s)

**ROI Proyectado:**
- **Inversión:** €3,200 desarrollo + €1,500/año operación
- **Ahorros:** €248,000/año (prevención rework + reducción búsquedas)
- **Retorno:** 16,533% ROI — Recuperación en <3 días

**Timeline:** 8 días laborables (2 sprints, 53 horas total)

---

## 📖 Orden de Lectura Recomendado

### **Antes de la Reunión** (Preparación)
1. Leer **[MEETING-CHECKLIST-SF.md](MEETING-CHECKLIST-SF.md)** completo
2. Imprimir 3 copias **[ONE-PAGER-AI.md](ONE-PAGER-AI.md)**
3. Revisar FAQs en **[EXECUTIVE-SUMMARY-AI.md](EXECUTIVE-SUMMARY-AI.md)** § 6

### **Durante la Reunión** (20 minutos)
1. Presentar **[EXECUTIVE-SUMMARY-AI.md](EXECUTIVE-SUMMARY-AI.md)** (slides)
2. Entregar **[ONE-PAGER-AI.md](ONE-PAGER-AI.md)** como handout
3. Tener **[12-ai-architecture.md](12-ai-architecture.md)** disponible para preguntas técnicas

### **Después de la Reunión** (Follow-up)
1. Email con PDFs adjuntos: Executive Summary + Architecture Spec
2. Actualizar `memory-bank/activeContext.md` con outcome
3. Si APPROVED → Crear tickets T-1801 a T-1907 en backlog

---

## 🔗 Referencias Cruzadas

**Documentación Relacionada:**
- [../../09-mvp-backlog.md](../../09-mvp-backlog.md) — US-018 (LangGraph) + US-019 (RAG) definidos
- [../../07-agent-design.md](../../07-agent-design.md) — Diseño original "The Librarian"
- [../../05-data-model.md](../../05-data-model.md) — Schema actual PostgreSQL

**Memory Bank:**
- [../../../memory-bank/activeContext.md](../../../memory-bank/activeContext.md) — Sprint 10 contexto
- [../../../memory-bank/progress.md](../../../memory-bank/progress.md) — Sprint 10 Day 1-2 completed

**Backlog:**
- **US-018:** LangGraph Agent "The Librarian" (21 SP, 28h, T-1801 a T-1806)
- **US-019:** RAG System "The Archivist" (25 SP, 40h, T-1901 a T-1907)

---

## 🚀 Próximos Pasos

**Status Actual:** Documentación completa ✅

**Pendiente:**
1. ⏳ Agendar reunión con Sagrada Família (target May 3-5)
2. ⏳ Decisión GO/NO-GO esperada
3. ⏳ Si aprobado → Sprint 10-11 implementación (May 6-15)

**Contacto:**
- Responsable: Pedro Cortes (AI4Devs TFM)
- Proyecto: Sagrada Família Parts Manager
- GitHub: [AI4Devs-finalproject](https://github.com/LIDR-academy/AI4Devs-finalproject)

---

> **💡 Tip:** Si eres nuevo en esta documentación, empieza por [README-AI-DOCS.md](README-AI-DOCS.md) que tiene guías de lectura según tu rol (stakeholder/técnico/developer/BIM manager).
