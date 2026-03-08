# Plan de Despliegue en Producción y Análisis del Agente "The Librarian"

**Proyecto:** Sagrada Família Parts Manager (SF-PM)
**Fecha:** 2026-02-27
**Deadline:** 2026-03-19 (3 semanas)
**Rol:** Senior Technical Project Manager + Software Architect

---

## Resumen Ejecutivo

SF-PM es un MVP académico (TFM) con 4 User Stories completadas, 419+ tests en verde y Dockerfiles de producción ya existentes. La arquitectura actual corre en Docker Compose local con 5 servicios: `backend` (FastAPI), `frontend` (React/Nginx), `agent-worker` (Celery), `redis` y `db` (PostgreSQL local, solo dev).

**Dado que Supabase ya gestiona PostgreSQL y Storage en la nube**, el despliegue a producción requiere únicamente publicar **3 servicios con URL pública**: el frontend estático, la API FastAPI y el worker Celery — con Redis gestionado como plugin.

La plataforma recomendada es **Railway.app** por ser la única opción que soporta múltiples servicios Docker con Redis plugin y sin tiempo de inactividad ("sleep"), con coste inicial cubierto por créditos gratuitos suficientes para el plazo de entrega.

"The Librarian" es actualmente un worker Celery rule-based (sin LLM). La integración más viable y de mayor valor con LangChain en 3 semanas es **Validation Explanation**: generar mensajes de error en lenguaje natural cuando la validación falla, llamando a un LLM solo en el camino de error (coste cero en el happy path).

---

## Fase 1: Plan de Despliegue en Producción

### 1.1 Plataforma Elegida: Railway.app + Vercel

#### Evaluación Comparativa

| Criterio | Railway | Render | Fly.io | Vercel |
|---|---|---|---|---|
| Soporte Docker multi-servicio | Excelente | Bueno | Requiere Fly.toml | Solo frontend |
| Redis incluido | Plugin nativo | No gratuito | No incluido | No aplica |
| Sleep en tier gratuito | No (créditos) | Sí (15 min) | No (3 VMs) | No aplica |
| Configuración inicial | Baja | Baja | Alta | Mínima |
| Coste estimado 3 semanas | $0–5 (créditos) | $0 (con sleep) | $0 (free tier) | $0 |
| Viabilidad para deadline | **ALTA** | MEDIA | MEDIA | Solo frontend |

**Decisión: Railway (backend + worker + Redis) + Vercel (frontend)**

Razones:
- Railway deploya directamente desde el target `prod` de cada Dockerfile
- Plugin Redis nativo: se añade en 1 click, expone `${{Redis.REDIS_URL}}` automáticamente
- Sin sleep: el backend y el worker estarán disponibles durante la evaluación del TFM
- Los $5 de crédito mensual gratuito cubren 3 semanas con instancias pequeñas
- Vercel es el mejor hosting para frontends estáticos Vite (CDN global, deploy instantáneo)

### 1.2 Arquitectura de Producción

```
┌─────────────────────────────────────────────────────────────────────┐
│                        INTERNET / BROWSER                           │
└──────────────────────┬────────────────────────────────┬─────────────┘
                       │ HTTPS                          │ HTTPS + WSS
                       ▼                                ▼
          ┌────────────────────────┐       ┌────────────────────────┐
          │  Vercel (CDN Global)   │       │  Railway Service:      │
          │  Frontend React SPA    │       │  FastAPI Backend       │
          │  nginx:alpine          │       │  :8000 (4 uvicorn)    │
          │  (static build)        │       │  Dockerfile: prod      │
          └────────────────────────┘       └────────────┬───────────┘
                       │                                │
                       │ API calls /api/*               │ CELERY_BROKER_URL
                       │                                ▼
                       │               ┌────────────────────────────┐
                       │               │  Railway Plugin: Redis 7   │
                       │               │  (managed, private URL)   │
                       │               └────────────┬───────────────┘
                       │                            │
                       │               ┌────────────▼───────────────┐
                       │               │  Railway Service:          │
                       │               │  Celery Agent Worker       │
                       │               │  concurrency=4             │
                       │               │  Dockerfile: prod          │
                       │               └────────────────────────────┘
                       │
           ┌───────────▼──────────────────────────────────────────┐
           │                  Supabase Cloud                       │
           │  ┌──────────────────┐   ┌──────────────────────────┐ │
           │  │  PostgreSQL 15   │   │  Supabase Storage        │ │
           │  │  (blocks,events) │   │  raw-uploads bucket      │ │
           │  │  RLS enabled     │   │  processed-geometry      │ │
           │  └──────────────────┘   └──────────────────────────┘ │
           │  ┌─────────────────────────────────────────────────┐  │
           │  │  Supabase Realtime (WebSocket → frontend)       │  │
           │  └─────────────────────────────────────────────────┘  │
           └───────────────────────────────────────────────────────┘
```

**Notas clave:**
- El servicio `db` de `docker-compose.yml` (postgres:15-alpine) **no existe en producción**. Se usa `SUPABASE_DATABASE_URL` directamente.
- Comunicación Backend → Celery via Redis privado de Railway (no expuesto públicamente).
- Supabase Realtime conecta directamente desde el browser (no pasa por el backend).

### 1.3 Paso a Paso: Despliegue Completo

#### PREREQUISITO — Rotar Credenciales Supabase (P0 de Seguridad)

Las credenciales fueron expuestas en el historial de git. Deben rotarse antes de cualquier despliegue:

```bash
# En el dashboard de Supabase:
# 1. Settings → Database → Reset database password
# 2. Settings → API → Regenerate service_role key
# 3. Actualizar .env local con los nuevos valores
# 4. Actualizar GitHub Secrets (SUPABASE_URL, SUPABASE_KEY, SUPABASE_DATABASE_URL)
```

#### Paso 1: Verificar que los Dockerfiles prod funcionan localmente

```bash
# Construir imagen de producción del backend
docker build --target prod -t sf-pm-backend:prod \
  --file src/backend/Dockerfile src/backend

# Construir imagen de producción del frontend
docker build --target prod -t sf-pm-frontend:prod \
  --file src/frontend/Dockerfile src/frontend

# Construir imagen de producción del agente
docker build --target prod -t sf-pm-agent:prod \
  --file src/agent/Dockerfile src/agent
```

#### Paso 2: Aplicar Migraciones a Supabase Cloud

Las migraciones SQL deben aplicarse manualmente a la base de datos cloud (no corren automáticamente sin el contenedor `db` local):

```bash
# Con psql y SUPABASE_DATABASE_URL (ver .env local)
psql $SUPABASE_DATABASE_URL \
  -f supabase/migrations/20260207133355_create_raw_uploads_bucket.sql

psql $SUPABASE_DATABASE_URL \
  -f supabase/migrations/20260211155000_create_blocks_table.sql

psql $SUPABASE_DATABASE_URL \
  -f supabase/migrations/20260211160000_add_validation_report.sql

psql $SUPABASE_DATABASE_URL \
  -f supabase/migrations/20260212100000_extend_block_status_enum.sql

psql $SUPABASE_DATABASE_URL \
  -f supabase/migrations/20260219000001_add_low_poly_url_bbox.sql

# Verificar que las tablas existen
psql $SUPABASE_DATABASE_URL -c "\dt"

# Alternativa: Supabase Dashboard → SQL Editor → pegar cada archivo en orden
```

Inicializar buckets de Storage:

```bash
# Ejecutar el script de inicialización con credenciales de producción
SUPABASE_URL=https://[tu-proyecto].supabase.co \
SUPABASE_KEY=[tu-service-role-key] \
  python infra/init_db.py
```

#### Paso 3: Crear proyecto en Railway

```bash
# Instalar Railway CLI
npm install -g @railway/cli

# Login y crear proyecto
railway login
railway init  # "Empty Project" → nombre: "sf-pm"
```

#### Paso 4: Añadir el Plugin de Redis

```
Dashboard Railway → proyecto "sf-pm" → New → Database → Add Redis
# Railway crea Redis 7 y expone la variable ${{Redis.REDIS_URL}}
# Formato: redis://:password@host:port
```

#### Paso 5: Desplegar el Backend (FastAPI)

Configuración en Railway Dashboard → New Service → GitHub Repo:
- **Root Directory:** `src/backend`
- **Dockerfile Path:** `Dockerfile`
- **Docker Target:** `prod`
- **Service Name:** `sf-pm-backend`

Variables de entorno (Railway → sf-pm-backend → Variables):

```
SUPABASE_URL          = https://[tu-proyecto].supabase.co
SUPABASE_KEY          = [service_role key — NO usar anon key]
DATABASE_URL          = postgresql://postgres:[pass]@[host]:5432/postgres?sslmode=require
CELERY_BROKER_URL     = ${{Redis.REDIS_URL}}
ALLOWED_ORIGINS       = https://sf-pm-frontend.vercel.app
ENVIRONMENT           = production
CDN_BASE_URL          = https://[tu-proyecto].supabase.co/storage/v1/object/public/processed-geometry
USE_CDN               = false
```

#### Paso 6: Desplegar el Agent Worker (Celery)

Configuración en Railway Dashboard → New Service → GitHub Repo:
- **Root Directory:** `src/agent`
- **Dockerfile Path:** `Dockerfile`
- **Docker Target:** `prod`
- **Service Name:** `sf-pm-agent-worker`
- **Start Command** (override): `celery -A celery_app worker --loglevel=warning --concurrency=4`

> El agent-worker NO expone ningún puerto HTTP. Railway lo tratará como background worker, lo cual es correcto.

Variables de entorno (Railway → sf-pm-agent-worker → Variables):

```
SUPABASE_URL            = https://[tu-proyecto].supabase.co
SUPABASE_KEY            = [service_role key]
DATABASE_URL            = postgresql://postgres:[pass]@[host]:5432/postgres?sslmode=require
CELERY_BROKER_URL       = ${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND   = ${{Redis.REDIS_URL}}
```

#### Paso 7: Desplegar el Frontend en Vercel

```bash
# Instalar Vercel CLI
npm install -g vercel

# Desde la carpeta del frontend
cd src/frontend
vercel login
vercel --prod
# Vercel detecta automáticamente Vite y ejecuta "npm run build"
# URL asignada: https://sf-pm-frontend.vercel.app (o similar)
```

Variables de entorno (Vercel → Settings → Environment Variables):

```
VITE_SUPABASE_URL      = https://[tu-proyecto].supabase.co
VITE_SUPABASE_ANON_KEY = [anon key — NOT service_role]
VITE_API_URL           = https://sf-pm-backend.up.railway.app
```

> **Atención:** En producción (build estático), el proxy de Vite dev server no funciona. El frontend debe usar `VITE_API_URL` como URL base absoluta para todas las llamadas a `/api/*`. Verificar que `src/frontend/src/services/upload.service.ts` y demás servicios usan `import.meta.env.VITE_API_URL` como prefijo cuando está definida.

#### Paso 8: Actualizar ALLOWED_ORIGINS en el Backend

Una vez obtenida la URL de Vercel, actualizar en Railway → sf-pm-backend → Variables:

```
ALLOWED_ORIGINS = https://sf-pm-frontend.vercel.app
```

El backend lee esta variable en `src/backend/main.py` para configurar el middleware de CORS. Sin esto, todas las llamadas del browser serán bloqueadas.

#### Paso 9: Actualizar GitHub Secrets para CI/CD

```
# GitHub → Settings → Secrets and variables → Actions:
SUPABASE_URL             → nueva URL de Supabase
SUPABASE_KEY             → service_role key rotada
SUPABASE_DATABASE_URL    → nueva connection string
```

Railway se conecta automáticamente a GitHub y redeploya al hacer push a `main`. No es necesario modificar el CI.

#### Paso 10: Verificar el Despliegue

```bash
# Infraestructura
curl https://sf-pm-backend.up.railway.app/health
# Esperado: {"status": "ok"}

curl https://sf-pm-backend.up.railway.app/ready
# Esperado: {"status": "ready", "checks": {"database": "ok", "redis": "ok"}}

# CORS (desde línea de comandos)
curl -H "Origin: https://sf-pm-frontend.vercel.app" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS \
     https://sf-pm-backend.up.railway.app/api/upload/url \
     -v 2>&1 | grep -i "access-control"
# Esperado: Access-Control-Allow-Origin: https://sf-pm-frontend.vercel.app
```

### 1.4 Variables de Entorno por Servicio

#### Backend (Railway: sf-pm-backend)

| Variable | Valor | Notas |
|---|---|---|
| `SUPABASE_URL` | `https://[proyecto].supabase.co` | |
| `SUPABASE_KEY` | `eyJ...` | service_role, NO anon |
| `DATABASE_URL` | `postgresql://postgres:[pass]@[host]:5432/postgres?sslmode=require` | SUPABASE_DATABASE_URL |
| `CELERY_BROKER_URL` | `${{Redis.REDIS_URL}}` | Variable reference de Railway |
| `ALLOWED_ORIGINS` | `https://sf-pm-frontend.vercel.app` | Sin wildcard en producción |
| `ENVIRONMENT` | `production` | Activa validación CORS estricta |
| `CDN_BASE_URL` | `https://[proyecto].supabase.co/storage/v1/object/public/processed-geometry` | |
| `USE_CDN` | `false` | `true` solo si se configura CloudFront |

#### Agent Worker (Railway: sf-pm-agent-worker)

| Variable | Valor | Notas |
|---|---|---|
| `SUPABASE_URL` | `https://[proyecto].supabase.co` | Igual que backend |
| `SUPABASE_KEY` | `eyJ...` | service_role |
| `DATABASE_URL` | `postgresql://...?sslmode=require` | Igual que backend |
| `CELERY_BROKER_URL` | `${{Redis.REDIS_URL}}` | |
| `CELERY_RESULT_BACKEND` | `${{Redis.REDIS_URL}}` | Mismo Redis para results |

#### Frontend (Vercel: sf-pm-frontend)

| Variable | Valor | Notas |
|---|---|---|
| `VITE_SUPABASE_URL` | `https://[proyecto].supabase.co` | Para cliente JS y Realtime |
| `VITE_SUPABASE_ANON_KEY` | `eyJ...` | anon key (pública) |
| `VITE_API_URL` | `https://sf-pm-backend.up.railway.app` | URL absoluta del backend |

### 1.5 Checklist de Verificación Post-Despliegue

#### Infraestructura
- [ ] `GET /health` → `{"status": "ok"}`
- [ ] `GET /ready` → `{"status": "ready", "checks": {"database": "ok", "redis": "ok"}}`
- [ ] Railway logs de `sf-pm-agent-worker`: `celery@hostname ready`
- [ ] Railway logs de Redis: ambos servicios conectados

#### CORS
- [ ] Peticiones `/api/*` desde `https://sf-pm-frontend.vercel.app` sin errores de CORS
- [ ] Header `Access-Control-Allow-Origin` presente en respuestas
- [ ] No hay preflights (OPTIONS) rechazados en DevTools → Network

#### Flujo Upload Completo
- [ ] Subir un `.3dm` de prueba desde la URL de Vercel
- [ ] Archivo llega a Supabase Storage (bucket `raw-uploads`)
- [ ] Bloque creado en tabla `blocks` con status `uploaded`
- [ ] Celery procesa la tarea: status cambia `uploaded` → `processing` → `validated`
- [ ] Frontend recibe notificación de validación (Supabase Realtime WebSocket)
- [ ] Dashboard 3D muestra la pieza en el canvas

#### Seguridad
- [ ] `ALLOWED_ORIGINS` no contiene `*` en producción
- [ ] Header `Strict-Transport-Security` presente en respuestas backend (HTTPS)
- [ ] Credenciales en `.env` local son **distintas** de las expuestas en git history
- [ ] Supabase: service_role key rotada
- [ ] Supabase: database password rotada
- [ ] GitHub Secrets actualizados con nuevas credenciales

---

## Fase 2: Evaluación del Agente "The Librarian"

### 2.1 Estado Actual del Agente

"The Librarian" es un **worker Celery rule-based** sin ninguna integración LLM. El flujo actual en `src/agent/tasks/file_validation.py`:

```
Celery Task: validate_file(part_id, s3_key)
    ├── DBService.update_block_status(part_id, "processing")
    ├── FileDownloadService.download_from_s3(s3_key)  → /tmp/*.3dm
    ├── RhinoParserService.parse_file(local_path)
    │   ├── rhino3dm.File3dm.Read()
    │   ├── UserStringExtractor.extract()
    │   └── → FileProcessingResult
    ├── NomenclatureValidator.validate()
    │   └── regex: r"^SF-[A-Z]{2,4}-[A-Z]{2,3}-\d{3}$"
    ├── GeometryValidator.validate()
    │   └── checks: IsValid, bbox, zero-volume
    ├── DBService.save_validation_report(report)
    └── DBService.update_block_status(part_id, "validated"|"error_processing")
```

**Dependencias LLM actuales:** ninguna. No existe `langchain`, `openai` ni `anthropic` en `src/agent/requirements.txt`.

### 2.2 Casos de Uso Evaluados

| Opción | Descripción | Valor | Viabilidad | Esfuerzo | Score |
|---|---|---|---|---|---|
| **A. Validation Explanation** | LLM explica en español POR QUÉ falló la validación | Alto | Alta | 1 día | **9/10** |
| **B. Metadata Enrichment** | LLM clasifica `tipologia` desde user strings extraídas | Medio | Alta | 2–3 días | 7/10 |
| **C. Nomenclature Suggestion** | LLM sugiere código ISO correcto cuando falla nomenclatura | Medio | Media | 3–4 días | 6/10 |
| **D. Natural Language Query** | Chat interface sobre el inventario de piezas (RAG) | Bajo | Baja | 1–2 semanas | 3/10 |

**Por qué la Opción A es la correcta:**
- El pipeline ya detecta errores con mensajes técnicos como `"Layer name 'sf-nav-col-001' does not match ISO-19650 pattern"`. El LLM solo transforma esa lista en texto explicativo para el arquitecto.
- **Coste LLM = 0 en el happy path** (solo se invoca cuando `errors != []`)
- Sin riesgo de regresión en la lógica de validación existente
- Demostrable visualmente durante la evaluación TFM
- La Opción D requiere RAG, vector store y UI de chat — fuera de alcance.

### 2.3 Arquitectura Propuesta: Validation Explanation

#### Estructura de archivos

```
src/agent/
├── services/
│   ├── validation_explainer.py   ← NUEVO
│   ├── nomenclature_validator.py  (sin cambios)
│   ├── geometry_validator.py      (sin cambios)
│   └── ...
└── tasks/
    └── file_validation.py         ← MODIFICADO (añadir ~10 líneas)
```

#### Nuevo servicio: `src/agent/services/validation_explainer.py`

```python
"""
Validation Explanation Service

Translates technical validation errors into human-readable Spanish explanations
using Claude Haiku via LangChain. Called ONLY when validation fails.
Zero cost on the happy path.
"""
import structlog
from typing import List

logger = structlog.get_logger()


class ValidationExplainer:
    """LLM-powered explainer for validation errors."""

    def __init__(self):
        from langchain_anthropic import ChatAnthropic
        self.llm = ChatAnthropic(
            model="claude-haiku-4-5",
            max_tokens=512,
            temperature=0.2,
        )

    def explain_errors(
        self,
        errors: List[dict],
        iso_code: str,
    ) -> str:
        """
        Generate plain-language explanation for validation errors.
        Returns "" if no errors or on LLM failure (graceful degradation).
        """
        if not errors:
            return ""

        error_text = "\n".join([
            f"- [{e['category'].upper()}] {e.get('target', 'unknown')}: {e['message']}"
            for e in errors
        ])

        prompt = f"""Eres un experto en BIM y la norma ISO-19650 para el proyecto Sagrada Família.

Se han detectado los siguientes errores de validación en la pieza {iso_code}:

{error_text}

Explica en 2-3 frases:
1. Qué significa cada error en términos prácticos para el arquitecto
2. Cómo corregirlo en Rhinoceros 3D

Sé conciso y técnicamente preciso. Responde en español."""

        try:
            from langchain_core.messages import HumanMessage
            response = self.llm.invoke([HumanMessage(content=prompt)])
            logger.info(
                "validation_explainer.success",
                iso_code=iso_code,
                error_count=len(errors),
            )
            return response.content
        except Exception as e:
            # LLM failure NEVER blocks validation results
            logger.warning("validation_explainer.failed", error=str(e))
            return ""
```

#### Modificación en `file_validation.py` (bloque final, ~10 líneas nuevas)

```python
# Después de ejecutar ambos validators y antes de save_validation_report:

all_errors = nomenclature_errors + geometry_errors
llm_explanation = ""

if all_errors:
    try:
        from services.validation_explainer import ValidationExplainer
        explainer = ValidationExplainer()
        llm_explanation = explainer.explain_errors(
            errors=[e.model_dump() for e in all_errors],
            iso_code=s3_key.split("/")[-1].replace(".3dm", ""),
        )
    except Exception as e:
        logger.warning("validation_explainer.skipped", error=str(e))

# Añadir al metadata del report si existe
if llm_explanation:
    metadata["llm_explanation"] = llm_explanation
```

#### Exposición en el Frontend

El campo `llm_explanation` queda disponible en `validation_report.metadata` (JSONB). El componente `PartDetailModal` (`src/frontend/src/components/`) ya muestra el `validation_report` en una pestaña — solo añadir un bloque condicional que renderice `metadata.llm_explanation` si existe.

### 2.4 Modelo LLM Recomendado

| Modelo | Coste Input | Coste Output | Latencia | Decisión |
|---|---|---|---|---|
| **Claude Haiku 4.5** | $0.25/M tokens | $1.25/M tokens | ~0.5s | **ELEGIDO** |
| GPT-4o-mini | $0.15/M tokens | $0.60/M tokens | ~0.5s | Alternativa válida |
| Claude Sonnet | $3/M tokens | $15/M tokens | ~1.5s | Excesivo para este caso |
| GPT-3.5-turbo | $0.50/M tokens | $1.50/M tokens | ~0.8s | Alternativa |

**Coste real estimado:** ~500 tokens × 50 uploads de prueba = 25,000 tokens = **$0.03 total**. Despreciable.

### 2.5 Dependencias Nuevas

Añadir a `src/agent/requirements.txt`:

```
# LangChain integration — Validation Explanation
langchain>=0.3.0
langchain-anthropic>=0.3.0
anthropic>=0.40.0
```

Nueva variable de entorno (Railway → sf-pm-agent-worker → Variables):

```
ANTHROPIC_API_KEY = sk-ant-...
```

> Si `ANTHROPIC_API_KEY` no está configurada, el servicio falla silenciosamente y la validación funciona normalmente sin explicación LLM. Permite despliegue incremental sin romper nada.

### 2.6 Estimación de Esfuerzo

| Tarea | Tiempo |
|---|---|
| Crear `validation_explainer.py` + tests con mock LLM | 3 h |
| Modificar `file_validation.py` + test integración con LLM real | 2 h |
| Actualizar `requirements.txt` + verificar Docker build | 1 h |
| Configurar `ANTHROPIC_API_KEY` en Railway + deploy | 30 min |
| Actualizar `PartDetailModal` para mostrar `llm_explanation` | 2 h |
| **Total** | **~8–9 horas (1 día de trabajo)** |

---

## Fase 3: Calendario de Ejecución

### Semana 1 (Feb 27 – Mar 5): Despliegue en Producción

**Objetivo:** SF-PM accesible desde URL pública con flujo de upload completo funcionando.

| Día | Tareas | Estimación |
|---|---|---|
| Jue 27 Feb | Rotar credenciales Supabase (DB password + service_role key). Actualizar `.env` local y GitHub Secrets. Verificar que CI sigue en verde. | 1–2 h |
| Vie 28 Feb | Aplicar las 5 migraciones SQL a Supabase cloud. Ejecutar `infra/init_db.py` en producción para crear buckets Storage. | 1–2 h |
| Sáb 1 Mar | Crear proyecto Railway. Añadir plugin Redis. Desplegar Backend service (`prod` target, configurar variables de entorno). Verificar `/health` y `/ready`. | 2–3 h |
| Dom 2 Mar | Desplegar Agent Worker service en Railway. Verificar logs: `celery@hostname ready`. Verificar conectividad Redis. | 1–2 h |
| Lun 3 Mar | Desplegar Frontend en Vercel. Configurar `VITE_API_URL` y `VITE_SUPABASE_*`. Actualizar `ALLOWED_ORIGINS` en Railway. Verificar CORS. | 1 h |
| Mar 4 Mar | Test E2E completo: subir `.3dm` real desde Vercel → validación → dashboard 3D. Debug de problemas de conectividad. | 2–3 h |
| Mié 5 Mar | Buffer para bugs de producción. Documentar URLs de producción. Actualizar `README.md` para evaluadores. | 1–2 h |

**Entregable:** URL pública funcional con flujo upload + validación completo.

### Semana 2 (Mar 6 – Mar 12): Estabilización + LangChain

**Objetivo:** Sistema estable en producción. "The Librarian" genera explicaciones LLM en errores de validación.

| Día | Tareas | Estimación |
|---|---|---|
| Jue 6 Mar | Monitorear producción: Railway logs, Supabase Storage usage. Resolver bugs críticos de la semana anterior. | 1–2 h |
| Vie 7 Mar | Implementar `src/agent/services/validation_explainer.py`. Tests unitarios con mock LLM (`unittest.mock`). | 3 h |
| Sáb 8 Mar | Modificar `file_validation.py` para llamar al explainer. Test de integración con LLM real (Anthropic API key en local). | 2 h |
| Dom 9 Mar | Actualizar `requirements.txt`. Verificar build Docker `prod` con nuevas dependencias. Actualizar `memory-bank/techContext.md`. | 1 h |
| Lun 10 Mar | Desplegar agente actualizado en Railway. Configurar `ANTHROPIC_API_KEY`. Verificar logs de explicación en primera validación con errores. | 1–2 h |
| Mar 11 Mar | Actualizar `PartDetailModal` frontend para mostrar `metadata.llm_explanation` si existe. | 2 h |
| Mié 12 Mar | Buffer. Evaluar si hay tiempo para US-007 (Cambio de Estado) u otra US del backlog. | Variable |

**Entregable:** "The Librarian" genera explicaciones humanas de errores en producción.

### Semana 3 (Mar 13 – Mar 19): Testing Final + Documentación

**Objetivo:** Sistema pulido y documentado para evaluación académica.

| Día | Tareas | Estimación |
|---|---|---|
| Jue 13 Mar | Suite completa de tests: `make test && make test-front`. Verificar que no hay regresiones. | 1–2 h |
| Vie 14 Mar | Test de carga manual: 5–10 archivos `.3dm` en paralelo. Verificar comportamiento Celery bajo carga. Revisar Railway resource usage. | 2 h |
| Sáb 15 Mar | Actualizar `README.md` con guía completa para evaluadores (cómo acceder, qué probar, arquitectura). | 2–3 h |
| Dom 16 Mar | Capturas de pantalla del sistema en producción. Completar `memory-bank/progress.md`. | 1–2 h |
| Lun 17 Mar | Preparar demo script: secuencia de pasos para mostrar el sistema durante la evaluación. | 1 h |
| Mar 18 Mar | Revisión final: URLs, credenciales de demo, flujo E2E desde browser limpio. | 1–2 h |
| Mié 19 Mar | **DEADLINE.** Sistema en producción, documentado y verificado. | — |

**Entregable:** MVP completamente documentado y verificado en producción.

---

## Apéndice A: Problemas Anticipados y Mitigaciones

| Problema | Probabilidad | Mitigación |
|---|---|---|
| Railway no encuentra Dockerfile en subdirectorio | Media | Configurar "Root Directory" en Railway dashboard (no raíz del repo) |
| `open3d` falla en build Railway (binarios grandes) | Media | El `prod` Dockerfile ya instala `libx11-6 libgl1 libgomp1`. Verificar que Railway no usa Alpine para el build context |
| Frontend intenta llamar a `http://backend:8000` (hostname Docker) en prod | Alta | En producción el proxy Vite no existe. Verificar que todos los servicios en `src/frontend/src/services/` usan `import.meta.env.VITE_API_URL` como prefijo |
| CORS bloquea peticiones desde Vercel | Media | Asegurarse de que `ALLOWED_ORIGINS` en Railway contiene **exactamente** la URL de Vercel (sin trailing slash) |
| Supabase Realtime no conecta en prod | Baja | Verificar que `VITE_SUPABASE_ANON_KEY` está configurada en Vercel (necesaria para WebSocket auth) |
| Agent worker sin acceso a Supabase Storage | Baja | El `s3_key` se genera en el backend al confirmar upload. Verificar que llega correcto al task Celery |
| LangChain añade latencia excesiva | Baja | `max_tokens=512`, ~0.5s latencia Haiku. Task timeout es 540s. Totalmente aceptable |
| `ANTHROPIC_API_KEY` no configurada en Railway | Probable (primeros despliegues) | Try/except en explainer: falla silenciosamente, validación funciona sin explicación LLM |

## Apéndice B: Comandos de Referencia Rápida

```bash
# Verificar salud del sistema en producción
curl https://sf-pm-backend.up.railway.app/health
curl https://sf-pm-backend.up.railway.app/ready

# Ver logs del agente en Railway CLI
railway logs --service sf-pm-agent-worker --tail 50

# Verificar conectividad Redis desde el agent (Railway shell)
railway shell --service sf-pm-agent-worker
$ redis-cli -u $REDIS_URL ping

# Re-desplegar backend sin rebuild
railway redeploy --service sf-pm-backend

# Test CORS desde línea de comandos
curl -H "Origin: https://sf-pm-frontend.vercel.app" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS \
     https://sf-pm-backend.up.railway.app/api/upload/url \
     -v 2>&1 | grep -i "access-control"

# Aplicar una migración individual a Supabase cloud
psql $SUPABASE_DATABASE_URL -f supabase/migrations/[nombre_archivo].sql

# Verificar tablas en Supabase cloud
psql $SUPABASE_DATABASE_URL -c "\dt"
```
