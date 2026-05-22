# SF-PM — Guion de la demo (Viernes 2026-05-22, 10:00)

> Duración objetivo: **12–15 min** (10 demo + 5 Q&A).
> Tono: relajado, conversacional. Vender el **cambio** (de archivo estático → inventario vivo) y **lo que puede construirse encima**. Hablar de "El Bibliotecario" y "El Archivista" como dos ayudantes — son los personajes que la gente recuerda.

---

## 0. Antes de empezar (5 min antes)

- [ ] `make up` — servicios arriba (frontend :5173, backend :8000, agent-worker, redis)
- [ ] **Cmd + Shift + R** en el navegador → refresca el panel de detalle con el tema oscuro
- [ ] Confirmar conteo: navegador o `docker compose exec -T backend python3 -c "from infra.supabase_client import get_supabase_client as S; print(S().table('blocks').select('id',count='exact').execute().count)"` → **289**
- [ ] Embeddings al día (`generate_embeddings.py`) — si no, el Archivista solo cubre 48/289
- [ ] Smoke test Archivista (copiar y pegar, 20 segundos):
   - `Cuantas piezas hay en el inventario` → esperado: **289**
   - `Cuantas piezas tienen resistencia C` → esperado: **195**
   - `Cuantas piezas tienen tramo 1` → esperado: **101**
- [ ] Abrir 3 pestañas: (1) dashboard, (2) este guion, (3) `pitch-deck.html` (F11 para fullscreen)
- [ ] Tener listo en local **un .3dm extra** para subir en vivo (un capitel pequeño — algo que valide rápido para el efecto "wow")

---

## 1. La frase de apertura

> **"Os enseño un inventario que se gestiona casi solo. Subes un archivo, dos ayudantes con IA hacen el trabajo aburrido, y tú le haces preguntas en lenguaje normal. Hoy ya funciona con 289 piezas reales — y esto es solo la punta del iceberg de lo que se puede construir encima."**

Variantes para abrir según audiencia:

- **Directivo / decisor**: "Hoy es manual y opaco. Os enseño cómo puede ser automático y conversacional, con una base que ya funciona y un techo muy alto."
- **Equipo técnico**: "Dos capas de IA encima del inventario: una que valida y clasifica cada pieza al entrar, otra que responde preguntas sobre todo el catálogo. Ambas funcionando en producción. Os la enseño."
- **Mixta (por defecto)**: la frase grande de arriba.

---

## 2. Estructura de los 12 minutos

| Min | Bloque | Slide | Acción |
|---|---|---|---|
| 0:00 | Apertura + situación de partida | 1–2 | Solo voz, slide visible |
| 1:30 | La idea | 3 | Los dos ayudantes |
| 3:00 | **El Bibliotecario** | 4–5 | Slide + DEMO 1 (subir .3dm en vivo) |
| 6:00 | **El Archivista** | 6 | Slide + DEMO 2 (chat con 3 preguntas) |
| 9:00 | Vuelta por la app | 7 | Demo: subir → ver → detalle → chat |
| 10:30 | Lo que ya funciona | 8 | Slide de cifras |
| 11:00 | **Punta del iceberg** | 9 | Slide de futuro — aquí entusiasmamos |
| 11:30 | Cierre | 10 | Frase final |
| 12:00 | Q&A | — | Apéndice técnico a mano |

---

## 3. El Bibliotecario en directo — 3 min

### Mensaje que se llevan
> "No es un script que parsea ficheros. Es un ayudante que mira la pieza, decide qué es, rellena los datos y deja un informe de lo que ha hecho. Como un becario que nunca se cansa y siempre apunta lo que decide."

### Caso A — Subir en vivo
1. **Acción**: arrastrar el .3dm extra al uploader del dashboard.
2. **Decir mientras sube**:
   > "Lo que está pasando ahora: el archivo se sube directo, sin pasar por el servidor — por eso da igual que sea grande. Y en cuanto llega, el Bibliotecario se pone a trabajar. Vamos a ver el resultado."
3. **Cambiar a pestaña detalle / esperar a que aparezca**.
4. **Decir cuando aparece `validated`**:
   > "Lo que acaba de pasar: el Bibliotecario ha mirado la geometría, ha decidido que es un capitel, ha rellenado los datos y ha firmado un informe. Todo en segundos. Vamos a abrirlo…"
5. **Abrir panel de detalle → tab Validación**:
   > "Aquí está el informe: la clasificación, el motivo por el que decidió que era un capitel, y todo el rastro de pasos que siguió. Esto es lo que una hoja de cálculo no os puede dar."

### Caso B — Por qué cuenta lo que importa (con una pieza ya validada)
1. Abrir una pieza ya validada (ej: `GLPER.A-PAE0720.0103`).
2. Decir:
   > "Pequeño detalle pero importante: la IA distingue las piezas reales de la geometría interna del archivo. En esta familia eso significa contar 91 piezas, no 1.288 cosas. Es el tipo de detalle que separa algo que parece que funciona de algo que funciona de verdad."

### Caso C — Cuenta sus decisiones (resaltar el informe)
1. En el mismo panel, ver el bloque de clasificación.
2. Decir:
   > "Fijaos: además de decir 'esto es un capitel', explica por qué — la geometría compleja, el rango de volumen… Si mañana queréis revisar una decisión rara, está todo apuntado. No es una caja negra."

### Una nota sobre el peso real

> "Una cosa importante: hoy esta capa pesa más como **validador** que como clasificador, porque el catálogo es bastante homogéneo. Pero el motor de clasificación está montado para mucho más — cuando las tipologías se diversifiquen o queramos taxonomías más finas, no hay que rehacer nada. Está listo."

---

## 4. El Archivista en directo — 3 min

### Mensaje que se llevan
> "Hablas con el inventario como hablarías con una persona. Y lo importante: solo te cuenta lo que sabe. Si no lo sabe, te lo dice. Si lo sabe, te enseña en qué se basó."

### Abrir el chat (botón flotante "💬 El Archivista")

### Secuencia recomendada (orden robusto para meeting)

> **Importante:** estos ejemplos están validados con el estado actual del sistema.
> Si justo antes de la reunión subes nuevas piezas, pueden variar los números.

### Pregunta 1 — Total inventario (riesgo mínimo)
> **"Cuantas piezas hay en el inventario"**

Resultado esperado:
> "En el inventario hay 289 piezas."

Qué decir:
> "Empiezo por una comprobación global. Esto no depende de top_k ni de semántica: es conteo real de inventario."

### Pregunta 2 — Propiedad global (resistencia)
> **"Cuantas piezas tienen resistencia C"**

Resultado esperado:
> "Hay 195 piezas con resistencia c en el inventario..."

Qué decir:
> "Aquí ya filtra por propiedad sobre todo el inventario. Los ejemplos son una muestra, pero el número es global."

### Pregunta 3 — Propiedad global (tramo)
> **"Cuantas piezas tienen tramo 1"**

Resultado esperado:
> "Hay 101 piezas con tramo 01 en el inventario..."

Qué decir:
> "Aunque escriba tramo 1, internamente normaliza y consulta el dato real en formato 01."

### Pregunta 4 — Propiedad global (material positivo)
> **"Cuantas piezas tienen material blavozy"**

Resultado esperado:
> "Hay 22 piezas con material blavozy en el inventario..."

Qué decir:
> "También funciona con material; de nuevo, conteo global y ejemplos verificables."

### Pregunta 5 — Caso negativo (no inventa)
> **"Cuantas piezas tienen material montjuic"**

Resultado esperado:
> "No hay piezas con material montjuic en el inventario actual."

Qué decir:
> "Este es el comportamiento clave: cuando no existe dato, lo dice claramente y no se inventa nada."

### Pregunta opcional de backup (si piden otra)
> **"Que piezas tienen elemento COS"**

Resultado esperado:
> "Hay 246 piezas con elemento cos en el inventario..."

### Y el siguiente nivel del Archivista

> "Lo que habéis visto son preguntas rápidas — más cómodas que componer un filtro en cinco pasos. Pero el mismo motor sirve para **generar documentación**: 'estado del tramo 2', 'piezas pendientes', 'informe del mes'. La salida deja de ser una frase y pasa a ser un reporte completo. Mismo motor, otra forma de salida."

---

## 5. Vuelta por la app — 1.5 min

Recorrer las partes rápido, una frase por cada una:

1. **Cargar archivos**:
   > "Arrastrar y soltar. El archivo se sube directo, sin pasar por el servidor — por eso da igual el tamaño."

2. **Canvas 3D**:
   > "289 piezas en una escena navegable. Click para seleccionar, zoom hasta el detalle."

3. **Filtros**:
   > "Filtrar por estado, material, tipo — y todos los campos los ha rellenado la IA, nadie a mano."

4. **Panel de detalle**:
   > "La ficha de cada pieza: visor 3D propio, datos, informe del Bibliotecario. Y el visor está pensado para crecer — el primer paso natural es **dimensionar con dos clicks** dentro del propio visor. Se acabaron las discusiones eternas sobre cotas."

5. **En vivo**:
   > "Si alguien sube algo ahora mismo, aparece sin tener que recargar. Tiempo real de serie."

---

## 6. Lo que ya funciona — 30 s

Slide de cifras. Decir:

> "289 piezas reales, todas clasificadas por la IA — cero campos a mano. Cada pieza con su informe, sus medidas y tres versiones 3D para que cargue rápido. **Esto no es una maqueta con datos inventados. Es inventario real, hoy.**"

> "Y una cosa importante: los datos los **curamos nosotros**. La IA hace el trabajo pesado, pero la integridad de la información sigue bajo nuestro control. Esa es la diferencia entre 'un catálogo automático' y un catálogo en el que se puede confiar."

---

## 7. La punta del iceberg — 1 min ⭐

> **Este es el slide importante. Aquí abres el apetito.**

Pasar al slide 9. Decir:

> "Y aquí está la mejor parte: lo que habéis visto es la base. Una vez que el inventario está vivo, los siguientes pasos son fáciles. Por ejemplo…"

Señalar 3 o 4 cajas del slide (las que mejor encajen con la audiencia). Estas son las que más resuenan:

> "**Dimensionado con clicks**: medir cotas dentro del visor con dos clicks. Acabar con esas discusiones eternas sobre medidas que nos comen tantas horas."

> "**Informes automáticos**: el Archivista no solo contesta, también genera reportes — 'estado del tramo 2', 'qué falta este mes'."

> "**De proyecto a obra completa**: lo que hoy es inventario de proyecto puede crecer hasta cubrir producción, fabricación y montaje. Planos, geometrías, información de industriales — todo en el mismo sitio."

> "Y luego están las que se prestan más solas: búsqueda por foto, detección de duplicados antes de tallar dos veces, app móvil para el operario en taller, histórico por pieza…"

Cerrar el bloque:
> "Cada una de estas hoy sería un proyecto entero. Encima de esta base, son semanas. Esa es la ganancia real."

---

## 8. Cierre — 30 s

> "Resumen: hoy tenéis una base que ya funciona — 289 piezas, dos agentes, una app que se entiende sola. Y un techo muy alto encima."

Pausa. Una respiración. Sonrisa.

> "¿Qué construimos primero?"

---

## Apéndice — Plan B / Contingencia

- **Si la subida en vivo tarda**: tener una pestaña con un block ya validado abierto y decir "mientras procesa el nuevo, miremos uno que ya pasó por el pipeline" → demo Caso B/C.
- **Si el Archivista da una respuesta floja**: cortar y volver al guion robusto en este orden:
   1. `Cuantas piezas hay en el inventario`
   2. `Cuantas piezas tienen resistencia C`
   3. `Cuantas piezas tienen tramo 1`
- **Si aparece un número inesperado**: decir "perfecto, se nota que acaba de entrar dato nuevo" y reforzar el mensaje de inventario vivo.
- **Si cae el tiempo real**: refresca, di "el backend procesó igualmente, solo es la conexión live al navegador" y abre un terminal mostrando el count.
- **Si tarda más de 5 segundos en responder**: verbaliza "mientras responde, os explico el criterio: consulta global y fuentes verificables" y mantén la narrativa sin silencio.
- **Si Q&A entra en tecnicismos**: tienes el apéndice de abajo y, para más detalle, [decisions.md](../../memory-bank/decisions.md) y [09-mvp-backlog.md](../09-mvp-backlog.md).

---

## Apéndice — Preguntas técnicas probables (por si alguien las pregunta)

> **Solo abrir esto si te lo piden.** En la demo principal no aparece nada de esto.

| Pregunta | Respuesta de 15 s |
|---|---|
| ¿Qué hay debajo del Bibliotecario? | LangGraph como motor de agente, con 7 nodos: extraer geometría → validar → clasificar → enriquecer → reporte → marcar. Cada nodo es un paso, el estado pasa entre ellos. |
| ¿Y la clasificación, cómo decide? | GPT-4 Turbo con un prompt que pide tipología + confianza + razonamiento. Si GPT-4 falla, hay un fallback regex. Circuit breaker para no quemar tokens. |
| ¿Qué hay debajo del Archivista? | RAG con búsqueda híbrida: regex para códigos ISO exactos + similitud coseno con pgvector para preguntas semánticas. GPT-4 sintetiza solo con los bloques recuperados, con system prompt anti-alucinación. |
| ¿Cómo evitáis alucinaciones? | Grounding obligatorio en `match_blocks()` + las fuentes se devuelven al usuario para verificación. Si no hay match relevante, el modelo está instruido a decirlo. |
| ¿Coste de OpenAI a escala? | `text-embedding-3-small` (≈$0.00002/1k tokens) para los embeddings, GPT-4-turbo en clasificación (1 llamada por pieza, una vez) y en cada pregunta del chat. Para miles de piezas: céntimos. |
| ¿Por qué Supabase? | Postgres + Storage + pgvector + Realtime + Auth en un solo plano. Cero glue code, cero servidores que mantener. |
| ¿Cómo escala a 10.000 piezas? | pgvector aguanta scan exacto hasta unas miles; para más, índice IVFFlat/HNSW — una migración. El pipeline es horizontalmente escalable vía workers. |
| ¿Cómo manejáis piezas modificadas? | Hoy: re-subir el archivo (deduplicación por nombre de definición). En el roadmap del iceberg: re-procesado por código. |
| ¿Stack completo? | Frontend React+TS+Vite+Three.js, backend FastAPI+Celery+Redis, agente LangGraph, datos en Supabase. CI en GitHub Actions, despliegue front en Vercel. |
