# Presentación SF-PM — Viernes 2026-05-22, 10:00

Tres archivos, tres usos:

| Archivo | Para qué | Cómo abrirlo |
|---|---|---|
| **[pitch-deck.html](pitch-deck.html)** | El deck visual que proyectas durante la demo. 10 slides, tono casual, mismo lenguaje visual que la app. | Doble clic → abre en navegador. Pulsa **F** para fullscreen. |
| **[demo-script.md](demo-script.md)** | Tu guion. Apertura, casos del Bibliotecario y del Archivista, timings, plan B, Q&A técnico opcional. | Léelo. Imprímelo o ábrelo en una segunda pantalla. |
| Este README | El mapa. | Lo estás leyendo. |

---

## Cómo navegar el deck

| Tecla | Acción |
|---|---|
| `→` · `Space` · `PgDn` | Siguiente slide |
| `←` · `PgUp` | Slide anterior |
| `Home` · `End` | Primer / último slide |
| `F` | Fullscreen on/off |
| Click derecho / izquierdo de la pantalla | Avanzar / retroceder |

Contador de slides abajo a la derecha. Funciona offline, sin dependencias externas.

---

## Estructura del deck (10 slides)

1. **Hook** — Un inventario que se gestiona casi solo.
2. **Situación de partida** — El inventario invisible.
3. **La idea** — Dos ayudantes, una herramienta (Bibliotecario / Archivista).
4. **Cómo encaja todo** — Diagrama amable de la arquitectura.
5. **El Bibliotecario** — Qué hace cuando entra una pieza.
6. **El Archivista** — Qué hace cuando preguntas algo.
7. **Las cuatro caras de la app** — Subir · Ver · Detalle · Chat.
8. **Lo que ya funciona** — Cifras: 289 piezas, 100% automático.
9. **Punta del iceberg** ⭐ — 9 ejemplos de lo que se puede construir encima.
10. **Cierre** — "Hoy la base. Lo divertido es lo que construimos encima."

> El slide 9 es el más importante. Es el que vende **potencial**, no producto.

---

## El día antes (jueves)

- [ ] **Embeddings al día**: `docker compose run --rm backend python /app/infra/generate_embeddings.py` → para que el Archivista cubra los 289.
- [ ] **Ensayo entero** del [demo-script.md](demo-script.md), reloj en mano. Apunta a 10 min de demo + 5 de Q&A.
- [ ] **Pre-validar las 3 preguntas del Archivista**: pruébalas en local, anota las respuestas, ten una "respuesta esperada" para no quedarte sorprendido en directo.
- [ ] **Tener un `.3dm` pequeño de ensayo** para subir en vivo (1–3 InstanceDefinitions). El efecto "watch this" del Bibliotecario procesando en directo es el momento más fuerte de la demo.
- [ ] **Cmd + Shift + R** en el navegador para que coja el panel de detalle dark.

## El día (viernes)

- [ ] 30 min antes: `make up`, abrir pestañas, fullscreen deck.
- [ ] 10 min antes: respiración, leer la línea de apertura una vez más, sonrisa.
- [ ] 5 min antes: cargar tu .3dm de ensayo en el cargador (no enviar todavía).
- [ ] Hora: enviar.

---

## La frase de apertura

> *"Os enseño un inventario que se gestiona casi solo. Subes un archivo, dos ayudantes con IA hacen el trabajo aburrido, y tú le haces preguntas en lenguaje normal. Hoy ya funciona con 289 piezas reales — y esto es solo la punta del iceberg de lo que se puede construir encima."*

Variantes según audiencia en [demo-script.md](demo-script.md#1-la-frase-de-apertura).

---

## Tono — qué sí y qué no

- ✅ Casual, conversacional, "qué ganas tú".
- ✅ Habla de **capacidades** ("hace esto", "puede preguntar aquello").
- ✅ Habla de **potencial** ("imaginad…", "encima de esto…").
- ❌ Sin jerga (LangGraph, pgvector, RAG, StateGraph) en lo hablado — está disponible en el apéndice solo si preguntan.
- ❌ Sin frases grandilocuentes ("cada piedra cuenta una historia", etc.).
- ❌ Sin meter cifras técnicas (1536-d, GPT-4 Turbo…) salvo que pregunten.

---

## Si algo se cae

Plan B detallado en [demo-script.md → Apéndice](demo-script.md#apéndice--plan-b--contingencia). Resumen:

- Subida lenta → abrir una pieza ya validada, hablar de su informe.
- Archivista raro → 5 preguntas pre-validadas el jueves.
- Tiempo real caído → terminal con `select count(*) from blocks` y "el backend procesó igualmente".
- Pregunta técnica fuerte → apéndice técnico del guion + `memory-bank/decisions.md` + `docs/09-mvp-backlog.md`.
