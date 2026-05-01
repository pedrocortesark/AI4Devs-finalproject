# 📋 CHECKLIST REUNIÓN SAGRADA FAMÍLIA — Arquitectura de IA

**Fecha:** 2026-05-01  
**Preparado por:** Pedro Cortes (AI4Devs TFM)  
**Objetivo:** Presentar propuesta de arquitectura híbrida LangGraph + RAG

---

## 📚 Materiales de Presentación

### Documentación Técnica
- ✅ **docs/12-ai-architecture.md** — Especificación completa (60 páginas)
  - Arquitectura LangGraph (8 nodos State Machine)
  - Sistema RAG (pgvector + OpenAI embeddings)
  - Código completo Python/TypeScript
  - Plan de testing (15 test cases)
  - Análisis de costes y ROI
  
- ✅ **docs/EXECUTIVE-SUMMARY-AI.md** — Resumen ejecutivo (15 páginas)
  - Formato problema-solución-ROI
  - Timeline 8 días (2 sprints)
  - FAQs para stakeholders
  - Métricas de éxito claras

### Referencias Rápidas
- ✅ **prompts.md** — Entry #243 (trazabilidad del análisis)
- ✅ **docs/00-index.md** — Índice actualizado con sección AI
- ✅ **memory-bank/activeContext.md** — Sprint 10 context

---

## 🎯 Mensajes Clave (Elevator Pitch 30 segundos)

> "SF-PM añade una capa de IA de dos niveles: **The Librarian** valida archivos .3dm en 10 segundos para prevenir €225k/año en errores, y **The Archivist** responde preguntas complejas del inventario reduciendo búsquedas de 3 horas a 10 segundos. ROI: 16,533% — recuperación en 3 días. Inversión: €1,500/año operativo."

---

## 📊 Datos Clave para Memorizar

### Impacto Económico
- 💰 **Ahorro anual:** €248,000 (€225k prevención errores + €15k tiempo + €8k reportes)
- 💸 **Inversión operativa:** €1,500/año (OpenAI API + infraestructura)
- 📈 **ROI:** 16,533% (recuperación en <3 días)

### Métricas Técnicas
- ⚡ **Tiempo validación:** 10 segundos (vs. 3 días manual)
- 🎯 **Accuracy LLM:** 95% (vs. 85% manual)
- 🔍 **Reducción tiempo búsqueda:** 97% (3 horas → 10 segundos)
- 🚫 **Tasa errores ingesta:** <1% (vs. 15% actual)

### Timeline Implementación
- 📅 **Sprint 10 (Semana 1-2):** LangGraph Agent (28 horas)
- 📅 **Sprint 11 (Semana 3):** RAG System (25 horas)
- 🎉 **Total:** 8 días laborables (53 horas)

---

## 🗣️ Script de Presentación (20 minutos)

### 1. Introducción (2 min)
- Contexto: MVP desplegado (5 US, 81 SP, https://sf-pm.vercel.app)
- Propósito reunión: Presentar arquitectura IA para comercialización

### 2. Problema Actual (3 min)
- ❌ 15% archivos con errores → €15k/pieza en retrabajo
- ❌ 3 horas/día buscando información
- ❌ 2 semanas generar reportes auditoría
- **Total pérdidas:** €248,000/año

### 3. Solución — Capa 1: The Librarian (5 min)
- **Qué hace:** Validación automática pre-ingesta (8 checks)
- **Tecnología:** LangGraph State Machine + GPT-4
- **Beneficio:** Previene errores antes de entrar al sistema
- **Demo:** [Mostrar diagrama state machine en docs/12-ai-architecture.md]

### 4. Solución — Capa 2: The Archivist (5 min)
- **Qué hace:** Asistente conversacional con búsqueda semántica
- **Tecnología:** RAG (pgvector + OpenAI embeddings)
- **Beneficio:** Búsquedas complejas en lenguaje natural
- **Demo:** [Mostrar ejemplos de consultas en EXECUTIVE-SUMMARY-AI.md]

### 5. ROI y Costes (3 min)
- Inversión desarrollo: €3,200 (8 días)
- Inversión operativa: €1,500/año
- Ahorro: €248,000/año
- **ROI: 16,533%**

### 6. Timeline y Próximos Pasos (2 min)
- Semanas 1-2: LangGraph Agent
- Semana 3: RAG System
- Semana 4: Testing + ajustes
- **Go-live:** 4 semanas desde aprobación

---

## ❓ Preguntas Anticipadas (Preparadas)

### Técnicas

**Q1: ¿Qué pasa si OpenAI tiene downtime?**
- ✅ Fallback automático a clasificación regex
- ✅ Validación nunca se bloquea
- ✅ Accuracy degrada temporalmente de 95% a 85%

**Q2: ¿Los datos de SF se envían a OpenAI?**
- ✅ Solo metadata (nombres, dimensiones) — NO geometría 3D completa
- ✅ OpenAI no entrena modelos con datos clientes (Enterprise policy)
- ✅ Opción alternativa: LLaMA 3.1 self-hosted (€200/mes, 100% privacidad)

**Q3: ¿El sistema puede "aprender" de correcciones manuales?**
- ✅ Sí (Fase 3 post-MVP)
- ✅ Fine-tuning GPT-4 con ejemplos validados de SF
- ✅ Human-in-the-loop feedback loop
- ✅ Target accuracy: 99%

**Q4: ¿Cómo se garantiza que el LLM no "alucina" información?**
- ✅ RAG busca primero en BD (contexto real)
- ✅ LLM genera respuesta SOLO con contexto encontrado
- ✅ Si no hay contexto → Responde "No tengo información"
- ✅ Tests de validación: 95% no-hallucination rate

**Q5: ¿Qué pasa con la privacidad/GDPR?**
- ✅ Embeddings no son reversibles (imposible reconstruir texto)
- ✅ RLS (Row Level Security) en Supabase
- ✅ Auditoría completa: Todos los queries registrados en tabla `events`
- ✅ Opción self-hosted disponible si requisito legal

### Negocio

**Q6: ¿Por qué no esperar a tener más datos antes de IA?**
- ✅ Validación activa previene errores AHORA (no reactivo)
- ✅ RAG funciona con dataset pequeño (100+ piezas suficiente)
- ✅ Cuanto antes se implemente, menos errores acumulados

**Q7: ¿Qué diferencia a SF-PM de otras herramientas BIM?**
- ✅ Específico para patrimonio arquitectónico único (no serializado)
- ✅ IA integrada desde diseño (no add-on)
- ✅ Validación activa pre-ingesta (vs. validación post-error)
- ✅ Open-source base (customizable para SF)

**Q8: ¿Cuál es el lock-in con OpenAI?**
- ✅ Bajo: API estándar (fácil cambiar a Claude, Gemini)
- ✅ Embeddings portables (estándar vector 1536D)
- ✅ Código 100% open-source
- ✅ Datos permanecen en Supabase (no vendor lock-in)

---

## ✅ Checklist Pre-Reunión (1 día antes)

### Preparación Técnica
- [ ] Laptop cargado + cargador backup
- [ ] Conexión internet estable verificada
- [ ] Navegador con tabs pre-abiertos:
  - [ ] docs/12-ai-architecture.md (especificación técnica)
  - [ ] docs/EXECUTIVE-SUMMARY-AI.md (resumen ejecutivo)
  - [ ] https://sf-pm.vercel.app (demo live MVP)
- [ ] Backup USB con PDFs de documentación (por si falla internet)

### Preparación de Contenido
- [ ] Imprimir 3 copias EXECUTIVE-SUMMARY-AI.md (para stakeholders)
- [ ] Preparar slide deck opcional (5 slides máximo):
  1. Problema (metrics actuales)
  2. Solución (diagrama arquitectura)
  3. ROI (tabla costes/ahorros)
  4. Timeline (gantt 8 días)
  5. Next steps (decision checklist)

### Preparación Personal
- [ ] Revisar docs/02-prd.md (recordar personas: María, Jordi, Carme)
- [ ] Memorizar 3 datos clave: €248k ahorro, 16,533% ROI, 8 días implementación
- [ ] Preparar anécdota: Caso real error nomenclatura → €15k pérdida

---

## 🎬 Checklist Durante Reunión

### Inicio (primeros 5 min)
- [ ] Presentación personal breve (30 seg: nombre, rol, contexto TFM)
- [ ] Agenda rápida (3 puntos: problema, solución, ROI)
- [ ] Preguntar: "¿Cuánto tiempo tenemos?" (ajustar ritmo)

### Durante Presentación
- [ ] Mantener contacto visual (no leer slides)
- [ ] Pausar cada 5 min para preguntas
- [ ] Usar whiteboard si disponible (dibujar state machine)
- [ ] Tomar notas de objeciones/preguntas

### Cierre (últimos 5 min)
- [ ] Resumen 3 puntos clave (problema → solución → ROI)
- [ ] Próximos pasos claros:
  1. Decisión GO/NO-GO (fecha límite: 3-5 días)
  2. Si GO: Provisión OpenAI API key
  3. Si GO: Test dataset (50 preguntas + 100 .3dm históricos)
- [ ] Agradecer tiempo
- [ ] Dejar PDFs impresos + tarjeta contacto

---

## 📧 Checklist Post-Reunión (mismo día)

### Follow-up Inmediato
- [ ] Email thank-you (máx. 2 horas después)
- [ ] Adjuntar:
  - [ ] docs/12-ai-architecture.md (PDF)
  - [ ] docs/EXECUTIVE-SUMMARY-AI.md (PDF)
  - [ ] Link GitHub repo (si solicitado)
- [ ] Resumir acuerdos alcanzados
- [ ] Confirmar next steps + deadlines

### Documentación Interna
- [ ] Actualizar prompts.md con outcome reunión
- [ ] Actualizar memory-bank/activeContext.md:
  - Status: APPROVED / PENDING / REJECTED
  - Fecha decisión esperada
  - Ajustes solicitados
- [ ] Si APPROVED: Crear tickets T-1801 a T-1907 en backlog
- [ ] Si REJECTED: Documentar razones + lecciones aprendidas

---

## 🚀 Aprobación Pathway (si GO decision)

### Día 0: Aprobación
- [ ] Email confirmación recibido
- [ ] OpenAI API key provisioned (o aprobación €195/mes)
- [ ] Acceso a test dataset (100 .3dm + 50 preguntas)

### Día 1-2: Setup
- [ ] Crear branch `feature/langgraph-agent`
- [ ] Enable pgvector en Supabase
- [ ] Configurar OpenAI API en Railway env vars
- [ ] Kick-off meeting con equipo técnico SF (opcional)

### Día 3-7: Sprint 10 — LangGraph
- [ ] T-1801 a T-1806 completados
- [ ] Checkpoint demo (día 4): Validación funcional

### Día 8-10: Sprint 11 — RAG
- [ ] T-1901 a T-1907 completados
- [ ] Demo final (día 10): Sistema completo

### Día 11: Go-Live
- [ ] Deploy a producción
- [ ] Training sesión con BIM Managers (1 hora)
- [ ] Monitoreo 24h post-deployment

---

## 📌 Recordatorios Críticos

### NO hacer:
- ❌ No prometer fechas sin validar con equipo técnico
- ❌ No criticar soluciones actuales de SF (enfoque positivo)
- ❌ No sobrecargar con jerga técnica (adaptar a audiencia)
- ❌ No olvidar mencionar que es proyecto TFM académico (transparencia)

### SÍ hacer:
- ✅ Escuchar activamente (pausar para preguntas)
- ✅ Validar understanding ("¿Tiene sentido esto para vosotros?")
- ✅ Conectar con pain points reales (María, Jordi, Carme)
- ✅ Mostrar entusiasmo (pero profesional)
- ✅ Agradecer oportunidad de presentar

---

## 🎯 Definición de Éxito de Reunión

**Éxito Mínimo (aprobado):**
- [ ] Stakeholders entienden problema y solución propuesta
- [ ] No hay objeciones técnicas bloqueantes
- [ ] Timeline 8 días aceptado como realista
- [ ] **Outcome:** "Nos interesa, necesitamos revisarlo internamente"

**Éxito Ideal (home run):**
- [ ] Aprobación verbal GO en reunión
- [ ] Fecha kick-off confirmada (próxima semana)
- [ ] OpenAI API key promised dentro de 48h
- [ ] Test dataset access granted
- [ ] **Outcome:** "Empecemos el lunes, ¿cómo os organizáis?"

**Red Flags (riesgo):**
- [ ] Preguntas sobre presupuesto sin responder
- [ ] Comparación con "solución que ya estamos evaluando"
- [ ] "Muy interesante, ya os llamaremos" (sin fecha)
- [ ] Preocupación por vendor lock-in sin resolver

---

**ÚLTIMA REVISIÓN:** 1 día antes de reunión  
**CONTACTO EMERGENCIA:** [tu-teléfono] (por si cambio de hora/sala)

---

_Checklist preparado para maximizar probabilidad de aprobación GO_  
_Versión: 1.0 | Autor: Pedro Cortes | Proyecto: AI4Devs TFM_
