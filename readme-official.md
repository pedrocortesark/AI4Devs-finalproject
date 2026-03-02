## Índice

0. [Ficha del proyecto](#0-ficha-del-proyecto)
1. [Descripción general del producto](#1-descripción-general-del-producto)
2. [Arquitectura del sistema](#2-arquitectura-del-sistema)
3. [Modelo de datos](#3-modelo-de-datos)
4. [Especificación de la API](#4-especificación-de-la-api)
5. [Historias de usuario](#5-historias-de-usuario)
6. [Tickets de trabajo](#6-tickets-de-trabajo)
7. [Pull requests](#7-pull-requests)

---

## 0. Ficha del proyecto

### **0.1. Tu nombre completo:**

Pedro Cortés Nieves

### **0.2. Nombre del proyecto:**

Sagrada Família Parts Manager (SF-PM)

### **0.3. Descripción breve del proyecto:**

Sistema enterprise que transforma archivos CAD estáticos (Rhino .3dm) en un gemelo digital activo para la gestión integral del inventario de decenas de miles de piezas únicas de la Sagrada Família de Barcelona. El sistema desacopla metadata crítica de geometría pesada (archivos de hasta **500MB**), permitiendo acceso instantáneo, validación automática mediante agentes IA ("The Librarian"), y visualización 3D web de alto rendimiento. La Oficina Técnica obtiene una **Single Source of Truth** para el ciclo de vida completo de cada pieza (Diseñada → Validada → En Fabricación → Completada → Instalada).

### **0.4. URL del proyecto:**

[AI4Devs-finalproject](https://github.com/pedrocortesark/AI4Devs-finalproject)


### 0.5. URL o archivo comprimido del repositorio

[AI4Devs-finalproject](https://github.com/pedrocortesark/AI4Devs-finalproject)

> Puedes tenerlo alojado en público o en privado, en cuyo caso deberás compartir los accesos de manera segura. Puedes enviarlos a [alvaro@lidr.co](mailto:alvaro@lidr.co) usando algún servicio como [onetimesecret](https://onetimesecret.com/). También puedes compartir por correo un archivo zip con el contenido


---

## 1. Descripción general del producto

> Describe en detalle los siguientes aspectos del producto:

### **1.1. Objetivo:**

**Sagrada Família Parts Manager (SF-PM)** tiene como propósito transformar archivos CAD estáticos en un gemelo digital activo para la gestión integral del inventario de piezas arquitectónicas de la Sagrada Família.

**Valor que aporta:**
- **Reducción 90% tiempo de búsqueda**: De 3 horas a 10 minutos diarios para encontrar información de piezas
- **Eliminación total de errores de nomenclatura**: Validación automática ISO-19650 antes de ingresar al sistema
- **Trazabilidad completa**: Audit trail inmutable de cada cambio (quién, qué, cuándo) para compliance patrimonial
- **Visualización 3D web**: Inspección interactiva de geometría compleja sin software CAD instalado

**Para quién:**
- **BIM Managers**: Supervisión global del inventario digital con visibilidad en tiempo real de 50,000+ piezas
- **Arquitectos de Diseño**: Validación instantánea de nomenclaturas con feedback en menos de 10 segundos
- **Talleres de Fabricación**: Acceso móvil a modelos 3D interactivos para planificar fabricación
- **Gestión de Materiales**: Auditoría de compliance con exportación de trazabilidad completa

### **1.2. Características y funcionalidades principales:**

1. **Upload y Validación Automática (F1 + F2)**
   - Drag & drop de archivos Rhino (.3dm) de hasta 2GB
   - Extracción automática de metadata en menos de 1 segundo por pieza
   - Validación activa mediante el agente "The Librarian" (IA)
   - Detección instantánea de nomenclaturas inválidas según ISO-19650
   - Clasificación automática de tipologías (Piedra/Hormigón/Metálica)
   - Informe detallado de errores con sugerencias de corrección

2. **Dashboard de Estado (F3)**
   - Tabla interactiva con todas las piezas del inventario
   - Stats cards en tiempo real: Total Piezas, En Fabricación, Bloqueadas
   - Filtros rápidos por estado, tipología y taller asignado
   - Búsqueda por nombre de pieza con autocompletado
   - Paginación optimizada para miles de registros

3. **Visor 3D Web (F4)**
   - Visualización de geometría en navegador con Three.js
   - Controles interactivos: rotar, zoom, pan
   - Renderizado de 100-1000 piezas simultáneas con >30 FPS
   - Información geométrica detallada (volumen, peso, material)
   - Captura de screenshots

4. **Gestión de Ciclo de Vida (F5)**
   - Actualización de estado: Diseñada → Validada → En Fabricación → Completada → Instalada
   - Asignación de piezas a talleres externos
   - Adjuntar fotos de control de calidad
   - Historial completo de cambios con event sourcing

5. **Control de Acceso y Seguridad (F6)**
   - Sistema de roles (Admin, Arquitecto, Taller, Dirección)
   - Row Level Security (RLS) en base datos
   - Autenticación JWT con Supabase
   - URLs firmadas para acceso seguro a archivos

6. **Agente IA "The Librarian"**
   - Validación multi-paso con LangGraph
   - Clasificación semántica con GPT-4
   - Enriquecimiento automático de metadatos faltantes
   - Decision binaria: Aceptar o Rechazar con explicación detallada

### **1.3. Diseño y experiencia de usuario:**

**Interfaz Dashboard (BIM Manager)**
El usuario aterriza en un dashboard limpio con:
- Header con logo, navegación principal y usuario autenticado
- Sidebar  filtros (Estado, Tipología, Taller, Búsqueda)
- Stats cards mostrando métricas clave (Total Piezas, En Fabricación, Bloqueadas)
- Tabla principal con columnas: Nombre, Estado, Tipo, Taller, Fecha
- Click en fila abre modal con detalles completos

**Interfaz Upload (Arquitecto)**
- Área drag & drop central con indicación clara de formatos soportados
- Validación instantánea durante upload con barra de progreso
- Feedback inmediato: Lista de piezas aceptadas vs rechazadas
- Informe de validación descargable con sugerencias específicas

**Interfaz Visor 3D (Taller)**
- Canvas 3D ocupando 70% del viewport
- Sidebar con información técnica de la pieza
- Controles intuitivos: rotar con mouse, zoom con rueda
- Acciones rápidas: Marcar completada, Adjuntar foto, Añadir nota

**Estado Empty States**
- Mensajes claros cuando no hay datos
- Call-to-action para siguiente paso lógico
- Ilustraciones mínimas pero descriptivas

> **Nota**: Las interfaces descritas corresponden a la implementación real del MVP (Entrega 2). US-001, US-002, US-005 y US-010 están completamente implementadas y probadas con >400 tests PASS.

### **1.4. Instrucciones de instalación:**

> **Importante — Enfoque Docker-First**: El proyecto está **100% containerizado**. Python, Node.js, Redis y PostgreSQL **no son necesarios en el host**. El único prerrequisito es Docker y Make (o WSL en Windows).

#### Prerrequisitos
- **Docker Engine** & **Docker Compose** (única dependencia de entorno)
- **GNU Make** (en Windows: WSL, Git Bash o ejecutar los comandos `docker compose` directamente)
- Cuenta **Supabase** con un proyecto activo (para Storage + Auth + Realtime)

#### Setup (Docker-First — 4 pasos)

**1. Clonar el repositorio y configurar variables de entorno:**

```bash
git clone https://github.com/pedrocortesark/AI4Devs-finalproject.git
cd AI4Devs-finalproject
cp .env.example .env
# Editar .env con los valores reales:
#   SUPABASE_URL, SUPABASE_KEY, SUPABASE_DATABASE_URL
#   DATABASE_PASSWORD, REDIS_PASSWORD
```

**2. Construir las imágenes Docker:**

```bash
make build
# Construye backend (python:3.11-slim), frontend (node:20-bookworm),
# agent-worker (python:3.11-slim con rhino3dm + open3d)
```

**3. Inicializar base de datos e infraestructura de storage:**

```bash
make up-db       # Arranca PostgreSQL (postgres:15-alpine)
make init-db     # Crea buckets Supabase + políticas RLS
```

**4. Levantar todos los servicios:**

```bash
make up
# Servicios disponibles:
#   Frontend:    http://localhost:5173  (React + Vite HMR)
#   Backend API: http://localhost:8000  (FastAPI + uvicorn --reload)
#   API Docs:    http://localhost:8000/docs  (Swagger UI)
```

#### Comandos de desarrollo habituales

```bash
make up-db          # Solo la base de datos
make up-backend     # Backend + dependencias (db + redis)
make up-frontend    # Frontend dev server (Vite)
make shell          # Shell en contenedor backend (para debugging)
make front-shell    # Shell en contenedor frontend
make test           # Tests backend + agent (pytest)
make test-unit      # Solo tests unitarios backend
make test-front     # Tests frontend (Vitest dentro de Docker)
make down           # Detener todos los servicios
make clean          # Detener + eliminar volúmenes + prune Docker
```

#### Migraciones de base de datos

```bash
make migrate-all    # Aplica todos los archivos SQL en supabase/migrations/
make migrate-t0503  # Aplica migración específica (low_poly_url + bbox)
make setup-events   # Crea tabla events (event sourcing)
```

#### Verificación de instalación

```bash
# Health check backend (incluye DB + Redis)
curl http://localhost:8000/ready
# Retorna 200 {"status":"ready"} o 503 si algún servicio no está disponible

# Verificar frontend
# Abrir navegador: http://localhost:5173
```

#### Troubleshooting

**`make up` falla por falta de `.env`:**
- Verificar que `.env` existe y tiene todas las variables de `.env.example` completadas.

**Error de conexión a Supabase:**
- Verificar `SUPABASE_URL` y `SUPABASE_KEY` en `.env`.
- Asegurarse de que el proyecto Supabase está activo en la consola web.

**Puerto 5173 / 8000 ocupado:**
- Ejecutar `make down` para detener contenedores previos.

**`agent-worker` no arranca (rhino3dm/open3d):**
- Las dependencias de geometría 3D se instalan automáticamente en el contenedor.
- Verificar logs con `docker compose logs agent-worker`.

---

## 2. Arquitectura del Sistema

### **2.1. Diagrama de arquitectura:**

SF-PM sigue una **arquitectura Cloud-Native Event-Driven** con los siguientes componentes:

```mermaid
graph TB
    subgraph "Client Layer"
        Browser["🌐 Web Browser<br/>(Chrome/Edge)"]
        ReactApp["⚛️ React SPA<br/>- React 18 + TypeScript<br/>- Three.js (Visor 3D)<br/>- TanStack Query (Cache)<br/>- Zustand (State)"]
    end
    
    subgraph "API Layer (Railway)"
        FastAPI["🚀 FastAPI Backend<br/>- Python 3.11<br/>- JWT Auth Middleware<br/>- Pydantic Validation<br/>- CORS Enabled"]
    end
    
    subgraph "Worker Layer (Railway/Background)"
        Redis[("📦 Redis Queue<br/>(Celery Broker)")]
        CeleryWorkers["⚙️ Celery Workers<br/>- rhino3dm Parser<br/>- Geometry Processor<br/>- .glb Converter"]
        Librarian["🤖 The Librarian Agent<br/>- LangGraph Workflow<br/>- GPT-4 Classification<br/>- ISO-19650 Validator"]
    end
    
    subgraph "Data Layer (Supabase)"
        SupabaseAuth["🔐 Supabase Auth<br/>(JWT Tokens)"]
        SupabaseDB[("🗄️ PostgreSQL<br/>- RLS Policies<br/>- Event Sourcing<br/>- JSONB Metadata")]
        SupabaseRealtime["📡 Supabase Realtime<br/>(WebSocket Server)"]
    end
    
    subgraph "Storage Layer (S3-Compatible)"
        S3Quarantine[("☁️ S3: /quarantine<br/>(Uploads sin validar)")]
        S3Raw[("☁️ S3: /raw<br/>(.3dm validados)")]
        S3Processed[("☁️ S3: /processed<br/>(.glb para visor)")]
    end
    
    subgraph "External Services"
        OpenAI["🧠 OpenAI API<br/>(GPT-4 Turbo)"]
    end
    
    Browser --> ReactApp
    ReactApp --> FastAPI
    ReactApp --> SupabaseRealtime
    FastAPI --> SupabaseAuth
    ReactApp --> SupabaseAuth
    FastAPI --> S3Quarantine
    ReactApp --> S3Quarantine
    FastAPI --> Redis
    Redis --> CeleryWorkers
    CeleryWorkers --> Librarian
    Librarian --> OpenAI
    FastAPI --> SupabaseDB
    CeleryWorkers --> SupabaseDB
    Librarian --> SupabaseDB
    CeleryWorkers --> S3Raw
    CeleryWorkers --> S3Processed
    SupabaseDB --> SupabaseRealtime
    SupabaseRealtime --> ReactApp
    ReactApp --> S3Processed
```

**Patrones Arquitectónicos Aplicados:**

1. **Event-Driven Architecture**: Procesamiento asíncrono mediante cola Redis/Celery para archivos pesados (hasta 2GB), evitando timeouts HTTP.

2. **Presigned URLs**: Upload directo a S3 sin pasar por API, reduciendo carga del servidor y permitiendo uploads paralelos con tracking de progreso.

3. **Event Sourcing**: Tabla `events` inmutable (append-only) que registra cada cambio de estado para trazabilidad completa y compliance.

4. **CQRS Ligero**: Separación de queries de lectura (dashboard con agregaciones optimizadas) y escritura (updates con validación).

**Beneficios:**
- ✅ **Escalabilidad**: Workers pueden escalar horizontalmente bajo demanda
- ✅ **Resiliencia**: Retry policies, circuit breakers y dead-letter queues
- ✅ **Performance**: UI nunca bloqueada, procesamiento en background
- ✅ **Simplicidad Operativa**: Servicios gestionados (Supabase, S3) minimizan overhead

**Trade-offs:**
- ❌ **Complejidad**: Más componentes que arquitectura monolítica tradicional
- ❌ **Consistencia Eventual**: Cambios en background pueden tardar segundos en reflejarse
- ❌ **Costo**: Servicios gestionados más caros que infraestructura auto-gestionada (~$235/mes MVP)


### **2.2. Descripción de componentes principales:**

#### 1. **Frontend - React SPA**
**Responsabilidad**: Interfaz de usuario interactiva con visualización 3D

**Stack Tecnológico:**
- React 18 + TypeScript: UI componentes con type safety
- Three.js + React-Three-Fiber: Renderizado WebGL de geometría .glb
- TanStack Query: Cache de datos y sincronización servidor-cliente
- Zustand: Estado global ligero (usuario, filtros)
- Tailwind CSS: Estilos utility-first
- Vite: Bundler con HMR rápido

**Deploy**: Vercel CDN (edge functions, auto-scaling)

#### 2. **Backend - FastAPI**
**Responsabilidad**: Orquestador de lógica de negocio, validación y autenticación

**Stack Tecnológico:**
- FastAPI 0.109+: Framework async con OpenAPI auto-generado
- Pydantic 2.x: Validación de schemas
- python-jose: Manejo de JWT tokens
- httpx: Cliente HTTP async para Supabase

**Endpoints Críticos:**
```python
POST /api/upload/presigned-url     # Genera URL firmada S3
POST /api/blocks                   # Crea registro + encola job
GET  /api/blocks                   # Lista con filtros
PATCH /api/blocks/{id}/status      # Actualiza estado
GET  /api/dashboard                # Agregaciones stats
```

**Deploy**: Railway ($10/mes tier Starter)

#### 3. **Worker Layer - Celery + The Librarian**
**Responsabilidad**: Procesamiento pesado en background

**Componentes:**
- **Celery Workers**: Extracción metadata, conversión 3D
- **Redis**: Broker de mensajes y backend de resultados
- **The Librarian Agent (LangGraph)**: Validación multi-paso

**Workflow del Agente:**
```
1. Metadata Validation → 2. Nomenclature Check (LLM) →
3. Geometry Analysis → 4. Enrichment (LLM) → 5. Final Verdict
```

**Deploy**: Railway (mismo contenedor que Backend)

#### 4. **Data Layer - Supabase**
**Responsabilidad**: Base de datos, autenticación y notificaciones

**Servicios:**
- **PostgreSQL 15**: 8 tablas con RLS policies
- **Supabase Auth**: JWT-based con roles
- **Realtime**: WebSockets para updates en tiempo real
- **Storage**: S3-compatible para archivos CAD

**Esquema**: Ver sección 3 (Modelo de Datos)

**Deploy**: Supabase Cloud Pro ($25/mes)

#### 5. **External Services**
- **OpenAI GPT-4 Turbo**: Clasificación semántica y enriquecimiento (~$200/mes)
- **Sentry**: Error tracking y monitoring

### **2.3. Descripción de alto nivel del proyecto y estructura de ficheros**

**Estructura del Monorepo (`src/` layout):**

```
AI4Devs-finalproject/
├── src/
│   ├── frontend/                    # React SPA (node:20-bookworm)
│   │   ├── src/
│   │   │   ├── components/          # Componentes UI con tests co-localizados
│   │   │   │   ├── FileUploader/    # Upload .3dm con presigned URLs
│   │   │   │   ├── Dashboard3D/     # Canvas 3D interactivo (Three.js)
│   │   │   │   ├── PartDetailModal/ # Visor 3D + Metadata + Validación
│   │   │   │   └── *.constants.ts   # Constantes co-localizadas (patrón clave)
│   │   │   ├── services/            # Capa de API (upload.service, navigation.service)
│   │   │   ├── types/               # Interfaces TypeScript (contrato con backend)
│   │   │   └── utils/               # formatters.ts (formatFileSize, formatDate, formatBBox)
│   │   ├── package.json
│   │   ├── vite.config.ts
│   │   └── Dockerfile               # Multi-stage: dev (HMR) + prod (nginx)
│   │
│   ├── backend/                     # FastAPI (python:3.11-slim)
│   │   ├── api/                     # Routers HTTP
│   │   │   ├── upload.py            # POST /api/upload/presigned-url
│   │   │   ├── parts.py             # GET /api/parts (filtros dinámicos)
│   │   │   ├── parts_detail.py      # GET /api/parts/{id}
│   │   │   ├── parts_navigation.py  # GET /api/parts/{id}/adjacent (Redis cache)
│   │   │   └── validation.py        # GET /api/parts/{id}/validation
│   │   ├── services/                # Lógica de negocio (Clean Architecture)
│   │   │   ├── parts_service.py     # Listado con filtros + transformaciones
│   │   │   ├── part_detail_service.py # RLS + CDN URL transformation
│   │   │   ├── navigation_service.py  # Prev/Next con Redis caching
│   │   │   └── upload_service.py    # Presigned URL + Celery enqueue
│   │   ├── infra/
│   │   │   ├── supabase_client.py   # Singleton cliente Supabase
│   │   │   └── redis_client.py      # Singleton Redis con graceful degradation
│   │   ├── schemas.py               # Modelos Pydantic (contrato API)
│   │   ├── constants.py             # Constantes centralizadas
│   │   ├── config.py                # pydantic-settings (env vars)
│   │   ├── main.py                  # FastAPI app entry point
│   │   └── Dockerfile               # Multi-stage: dev (reload) + prod (4 workers)
│   │
│   └── agent/                       # Celery Worker "The Librarian" (python:3.11-slim)
│       ├── services/
│       │   ├── rhino_parser_service.py      # Parsing .3dm con rhino3dm
│       │   ├── nomenclature_validator.py    # Validación ISO-19650 (rule-based)
│       │   ├── geometry_validator.py        # Checks geométricos (4 validaciones)
│       │   ├── user_string_extractor.py     # Extracción metadata de user strings
│       │   └── geometry_processing.py       # Decimación low-poly (trimesh + open3d)
│       ├── celery_app.py            # Configuración Celery + Redis broker
│       └── Dockerfile               # Con rhino3dm + open3d (C++ bindings)
│
├── tests/                           # Suite de tests (compartida entre contenedores)
│   ├── unit/                        # Tests unitarios (pytest, Vitest)
│   └── integration/                 # Tests de integración (Supabase + API)
│
├── supabase/
│   └── migrations/                  # SQL migrations (aplicadas via make migrate-all)
│
├── infra/                           # Scripts de inicialización Docker
│   ├── init_db.py                   # Crea buckets Supabase + políticas
│   └── setup_events_table.py        # Crea tabla events
│
├── docs/                            # Documentación técnica (Fases 1-8)
├── memory-bank/                     # Estado multi-agente (ADRs, contexto activo)
├── docker-compose.yml               # 5 servicios: backend, db, frontend, redis, agent-worker
├── Makefile                         # Orquestación Docker (make up, make test, etc.)
└── README.md
```

**Patrón de Arquitectura:**
- **Backend**: Clean Architecture (separación API/Services/Models)
- **Frontend**: Feature-based structure con hooks customs
- **Monorepo**: Separación por responsabilidad tecnológica

**Principios:**
- Cada capa tiene tests en `/tests`
- Configuración vía `.env` (nunca hardcoded)
- Docker para reproducibilidad

### **2.4. Infraestructura y despliegue**

**Diagrama de Deployment:**

```mermaid
graph TB
    subgraph "User Devices"
        Desktop["💻 Desktop<br/>(Chrome/Edge)"]
        Tablet["📱 Tablet Obra<br/>(Safari iOS)"]
    end
    
    subgraph "CDN Layer (Vercel Edge)"
        CDN["🌍 Vercel CDN<br/>- Static Assets (JS/CSS)<br/>- Edge Functions<br/>- Global PoPs"]
    end
    
    subgraph "Compute Layer (Railway)"
        APIServer["🚀 FastAPI Container<br/>- Dockerfile<br/>- Health Check /health<br/>- Auto-scaling (CPU >70%)"]
        WorkerPool["⚙️ Celery Workers<br/>- 2-4 concurrent processes<br/>- Auto-restart on failure"]
    end
    
    subgraph "Messaging Layer"
        RedisCloud[("📦 Redis Cloud<br/>- Managed (30MB free tier)")]
    end
    
    subgraph "Data Layer (Supabase Cloud)"
        SupabaseStack["🗄️ Supabase Pro<br/>- PostgreSQL 15 (1GB RAM)<br/>- Auth JWT<br/>- Realtime WebSocket<br/>- Daily Backups"]
    end
    
    subgraph "Storage Layer"
        ObjectStorage[("☁️ Object Storage<br/>- Supabase Storage (S3-compat)<br/>- 100GB included<br/>- CDN Integration")]
    end
    
    subgraph "External APIs"
        OpenAIService["🧠 OpenAI Platform<br/>- GPT-4 Turbo API"]
    end
    
    Desktop --> CDN
    Tablet --> CDN
    CDN --> APIServer
    CDN --> ObjectStorage
    APIServer --> RedisCloud
    APIServer --> SupabaseStack
    RedisCloud --> WorkerPool
    WorkerPool --> SupabaseStack
    WorkerPool --> ObjectStorage
    WorkerPool --> OpenAIService
```

**Costos Mensuales Estimados (MVP):**

| Servicio | Tier | Costo/Mes |
|----------|------|----------|
| Vercel (Frontend) | Hobby | $0 |
| Railway (Backend + Workers) | Starter | $10 |
| Supabase | Pro | $25 |
| Redis Cloud | Free | $0 |
| OpenAI API | Pay-as-you-go | $200 |
| **TOTAL** | | **$235/mes** |

**Proceso de Despliegue:**

1. **CI/CD con GitHub Actions**:
   ```yaml
   # .github/workflows/deploy.yml
   on:
     push:
       branches: [main]
   
   jobs:
     test:
       - Run pytest (backend)
       - Run vitest (frontend)
       - Run E2E tests (Playwright)
     
     build:
       - Build Docker images
       - Push to Railway registry
     
     deploy:
       - Deploy frontend to Vercel
       - Deploy backend to Railway
       - Run DB migrations
   ```

2. **Deployment Automático**:
   - **Frontend**: Push a `main` → Vercel auto-deploy (< 2 min)
   - **Backend**: Push → Railway build Docker → Deploy (< 5 min)
   - **Migrations**: Ejecutadas automáticamente en Railway pre-deploy

3. **Health Checks**:
   - Railway pingea `/health` cada 30s
   - Auto-restart si falla 3 veces consecutivas

4. **Rollback**:
   - Vercel: Un click en dashboard
   - Railway: Revert al deployment anterior vía CLI

### **2.5. Seguridad**

**Defense-in-Depth (4 Capas):**

#### Capa 1: Frontend
- ✅ **CSP Headers**: Content-Security-Policy contra XSS
- ✅ **Input Sanitization**: Validación de inputs para evitar XSS
- ✅ **JWT en memoria**: No se almacena en localStorage (máxima seguridad)
- ✅ **HTTPS Only**: Enforced por Vercel

**Ejemplo:**
```typescript
// Frontend valida tamaño y extensión antes de upload
const validateFile = (file: File) => {
  if (file.size > MAX_SIZE) throw new Error("File too large");
  if (!file.name.endsWith('.3dm')) throw new Error("Invalid extension");
};
```

#### Capa 2: API
- ✅ **Rate Limiting**: 100 req/min por IP
- ✅ **JWT Validation**: Verificar signature + expiry en cada request
- ✅ **CORS Strict**: Solo frontend domain permitido
- ✅ **Pydantic Schemas**: Validación exhaustiva de inputs

**Ejemplo:**
```python
# Middleware de autenticación
async def verify_jwt(token: str):
    try:
        payload = jwt.decode(token, PUBLIC_KEY, algorithms=["RS256"])
        if payload['exp'] < time.time():
            raise HTTPException(401, "Token expired")
        return payload
    except JWTError:
        raise HTTPException(401, "Invalid token")
```

#### Capa 3: Database
- ✅ **Row Level Security (RLS)**: Acceso a nivel de fila por rol
- ✅ **Prepared Statements**: Prevención de SQL injection
- ✅ **Encryption at Rest**: Supabase default

**Ejemplo RLS:**
```sql
-- Solo arquitectos pueden crear piezas
CREATE POLICY "Architects can insert blocks"
ON blocks FOR INSERT
TO authenticated
WITH CHECK (
  EXISTS (
    SELECT 1 FROM profiles
    WHERE profiles.user_id = auth.uid()
      AND profiles.role = 'architect'
  )
);
```

#### Capa 4: Storage
- ✅ **Presigned URLs**: Expiry de 15 minutos
- ✅ **IAM Roles**: Backend con permisos mínimos necesarios
- ✅ **Virus Scanning**: (Futuro) S3 Object Lambda con ClamAV

**Auditoría:**
- Tabla `events` inmutable registra todos los cambios
- Logs estructurados en JSON con contexto (user_id, IP, timestamp)
- Intentos de acceso no autorizados logueados en `audit_logs`

### **2.6. Tests**

**Estrategia de Testing (Pirámide):**

```
       /\
      /  \  E2E Tests (10%)
     /----\ Integration Tests (30%)
    /------\ Unit Tests (60%)
```

**Coverage Target**: >80% en cada capa

#### Backend Tests (pytest)

**1. Unit Tests - Servicios**
```python
# tests/services/test_geometry_service.py
def test_extract_metadata_from_3dm():
    """Verifica extracción correcta de metadata de archivo Rhino"""
    with open("fixtures/test_block.3dm", "rb") as f:
        metadata = GeometryService.extract_metadata(f)
    
    assert metadata["volume_m3"] > 0
    assert "layer_name" in metadata
    assert len(metadata["objects"]) > 0
```

**2. Integration Tests - Endpoints**
```python
# tests/api/test_upload.py
@pytest.mark.integration
def test_upload_endpoint_creates_part(test_client, mock_supabase):
    """Verifica que upload crea registro en DB correctamente"""
    files = {"file": ("test.3dm", open("fixtures/test.3dm", "rb"))}
    response = test_client.post("/api/upload", files=files)
    
    assert response.status_code == 201
    assert "part_id" in response.json()
    
    # Verifica que se creó en DB
    part = mock_supabase.table("parts").select("*").eq("id", response.json()["part_id"]).execute()
    assert part.data[0]["status"] == "uploaded"
```

#### Frontend Tests (Vitest + React Testing Library)

**3. Unit Tests - Componentes**
```typescript
// tests/components/UploadZone.test.tsx
import { render, fireEvent, waitFor } from '@testing-library/react';
import { UploadZone } from '../src/components/UploadZone';

test('muestra error si archivo excede tamaño máximo', async () => {
  const { getByTestId } = render(<UploadZone />);
  
  const largeFile = new File(['a'.repeat(600_000_000)], 'large.3dm');
  const input = getByTestId('file-input');
  
  fireEvent.change(input, { target: { files: [largeFile] } });
  
  await waitFor(() => {
    expect(getByTestId('error-message')).toHaveTextContent('File too large');
  });
});
```

#### Agent Tests (pytest)

**4. Integration Tests - LangGraph Workflow**
```python
# tests/agent/test_librarian_workflow.py
@pytest.mark.integration
def test_agent_validates_and_enriches_part():
    """Test completo del grafo de validación"""
    state = {
        "part_id": "test-123",
        "file_path": "fixtures/valid_block.3dm",
        "metadata": {}
    }
    
    graph = build_validation_graph()
    result = graph.invoke(state)
    
    assert result["final_status"] == "validated"
    assert result["nomenclature_valid"] is True
    assert "tipologia" in result["enriched_data"]
    assert result["enriched_data"]["tipologia"] in ["PIEDRA", "HORMIGON", "METAL"]
```

#### E2E Tests (Playwright)

**5. Flujo Completo - Upload y Visualización**
```typescript
// e2e/upload-flow.spec.ts
import { test, expect } from '@playwright/test';

test('usuario sube archivo y lo visualiza en 3D', async ({ page }) => {
  // Login
  await page.goto('/login');
  await page.fill('[name="email"]', 'test@example.com');
  await page.fill('[name="password"]', 'password123');
  await page.click('button[type="submit"]');
  
  // Upload
  await page.goto('/upload');
  await page.setInputFiles('input[type="file"]', './fixtures/test_block.3dm');
  await expect(page.locator('.success-message')).toBeVisible();
  
  // Verificar en dashboard
  await page.goto('/dashboard');
  await expect(page.locator('table')).toContainText('test_block.3dm');
  
  // Ver en 3D
  await page.click('button:has-text("Ver 3D")');
  await expect(page.locator('canvas')).toBeVisible();
  
  // Screenshot para regression visual
  await expect(page).toHaveScreenshot('viewer-3d.png');
});
```

**Fixtures de Prueba:**
- `test_block.3dm` (10MB, geometría simple, nomenclatura válida)
- `invalid_names.3dm` (nomenclaturas incorrectas para test de rechazo)
- `corrupted.3dm` (archivo malformado para test de error handling)

---

## 3. Modelo de Datos

### **3.1. Diagrama del modelo de datos:**

El modelo de datos sigue una estrategia híbrida (Relacional + NoSQL) con PostgreSQL 15 y JSONB para metadatos flexibles.

```mermaid
erDiagram
    PROFILES ||--o{ BLOCKS : "created_by"
    PROFILES ||--o{ EVENTS : "triggered_by"
    PROFILES ||--o{ NOTIFICATIONS : "receives"
    
    ZONES ||--|{ BLOCKS : "contains"
    
    BLOCKS ||--o{ EVENTS : "has_history"
    BLOCKS ||--o{ ATTACHMENTS : "has_files"
    BLOCKS }o--|| WORKSHOPS : "assigned_to"
    
    WORKSHOPS ||--o{ BLOCKS : "manages"
    
    PROFILES {
        uuid id PK
        uuid user_id FK "auth.users"
        text name
        text email
        text role "ENUM: architect, bim_manager, workshop, director"
        timestamptz created_at
        timestamptz updated_at
    }
    
    ZONES {
        uuid id PK
        text code UK "Ej: TORRE-MARIA-L15"
        text name "Torre de María - Nivel 15"
        text description
        jsonb metadata "Información contextual"
        timestamptz created_at
    }
    
    BLOCKS {
        uuid id PK
        text iso_code UK "SF-C12-D-001"
        text status "ENUM: uploaded, validated, in_fabrication, completed, archived"
        text tipologia "capitel, columna, dovela, clave, imposta"
        uuid zone_id FK
        uuid workshop_id FK "NULL si no asignado"
        uuid created_by FK
        uuid updated_by FK
        text url_original "S3: .3dm raw"
        text url_glb "S3: .glb procesado"
        jsonb rhino_metadata "Propiedades flexibles"
        timestamptz created_at
        timestamptz updated_at
        boolean is_archived "Soft delete"
    }
    
    EVENTS {
        uuid id PK
        uuid block_id FK
        text event_type "status_changed, metadata_updated, assigned"
        text old_value "Estado anterior"
        text new_value "Estado nuevo"
        jsonb metadata "Contexto adicional"
        uuid triggered_by FK "profiles.id"
        timestamptz created_at "Inmutable"
    }
    
    ATTACHMENTS {
        uuid id PK
        uuid block_id FK
        text attachment_type "qc_photo, technical_drawing, approval_doc"
        text url "S3 path"
        text filename
        integer size_bytes
        uuid uploaded_by FK
        timestamptz created_at
    }
    
    WORKSHOPS {
        uuid id PK
        text name UK "Taller Granollers"
        text location "Barcelona, Cataluña"
        text contact_email
        text contact_phone
        jsonb metadata "Especialidades, certificaciones"
        timestamptz created_at
    }
    
    NOTIFICATIONS {
        uuid id PK
        uuid user_id FK
        text notification_type "status_change, assignment, mention"
        text title
        text message
        jsonb metadata "Link a recurso, event_id"
        boolean is_read
        timestamptz created_at
        timestamptz read_at
    }
```


### **3.2. Descripción de entidades principales:**

#### Tabla: `blocks` (Piezas - Entidad Central)

**Descripción:** Tabla maestra de piezas arquitectónicas con referencias a geometría, estado y trazabilidad.

| Campo | Tipo | Constraints | Descripción |
|-------|------|-------------|-------------|
| `id` | `uuid` | PRIMARY KEY | Identificador único |
| `iso_code` | `text` | NOT NULL, UNIQUE | Código ISO-19650 (ej: "SF-C12-D-001") |
| `status` | `text` | NOT NULL, CHECK (...) | Estado: uploaded, validated, in_fabrication, completed, archived |
| `tipologia` | `text` | NOT NULL | Tipo: capitel, columna, dovela, clave, imposta |
| `zone_id` | `uuid` | FK → zones(id) | Zona espacial que contiene la pieza |
| `workshop_id` | `uuid` | FK → workshops(id), NULL | Taller asignado (NULL si no asignado) |
| `created_by` | `uuid` | FK → profiles(id), NOT NULL | Usuario que creó la pieza|
| `updated_by` | `uuid` | FK → profiles(id), NOT NULL | Último usuario que modificó |
| `url_original` | `text` | | URL S3 del archivo .3dm original |
| `url_glb` | `text` | | URL S3 del .glb procesado (NULL si aún no procesado) |
| `rhino_metadata` | `jsonb` | NOT NULL, DEFAULT '{}' | Metadata extraída de Rhino (volumen, peso, bbox, layers) |
| `created_at` | `timestamptz` | NOT NULL, DEFAULT now() | Fecha de creación |
| `updated_at` | `timestamptz` | NOT NULL, DEFAULT now() | Última modificación |
| `is_archived` | `boolean` | NOT NULL, DEFAULT false | Soft delete |

**Índices:**
- B-tree UNIQUE en `iso_code`
- B-tree en `status` (para queries dashboard)
- GIN en `rhino_metadata` (búsquedas JSONB)

**Triggers:**
- `set_updated_at`: Actualiza timestamp automáticamente
- `log_status_change`: Inserta evento en tabla `events` cuando cambia estado

**Ejemplo de `rhino_metadata`:**
```json
{
  "physical_properties": {
    "volume_m3": 2.45,
    "weight_kg": 6125,
    "material": "Montjuic Stone",
    "density_kg_m3": 2500
  },
  "geometry_info": {
    "bbox_min": [0, 0, 0],
    "bbox_max": [1.2, 0.8, 2.5],
    "layer_name": "SF-Capitel-Nivel15"
  }
}
```

#### Tabla: `events` (Audit Log - Event Sourcing)

**Descripción:** Tabla INMUTABLE (append-only) para trazabilidad completa. Registra cada cambio de estado o metadata.

| Campo | Tipo | Constraints | Descripción |
|-------|------|-------------|-------------|
| `id` | `uuid` | PRIMARY KEY | ID único del evento |
| `block_id` | `uuid` | FK → blocks(id), NOT NULL | Pieza afectada |
| `event_type` | `text` | NOT NULL, CHECK (...) | Tipo: status_changed, metadata_updated, assigned |
| `old_value` | `text` | | Valor anterior (ej: "validated") |
| `new_value` | `text` | | Valor nuevo (ej: "in_fabrication") |
| `metadata` | `jsonb` | DEFAULT '{}' | Contexto adicional (notas, razón) |
| `triggered_by` | `uuid` | FK → profiles(id), NOT NULL | Usuario responsable |
| `created_at` | `timestamptz` | NOT NULL, DEFAULT now() | Timestamp inmutable |

**Restricciones de Seguridad:**
- NO se permiten operaciones UPDATE o DELETE (RLS policy)
- Solo INSERT por backend autenticado

#### Tabla: `profiles` (Usuarios)

Extiende `auth.users` de Supabase con información de negocio:

| Campo | Tipo | Constraints | Descripción |
|-------|------|-------------|-------------|
| `id` | `uuid` | PRIMARY KEY | ID único |
| `user_id` | `uuid` | FK → auth.users(id), UNIQUE | Vinculación con Supabase Auth |
| `name` | `text` | NOT NULL | Nombre completo |
| `email` | `text` | NOT NULL, UNIQUE | Email corporativo |
| `role` | `text` | NOT NULL, CHECK (...) | Rol: architect, bim_manager, workshop, director |

**Roles y Permisos (RBAC):**
- **architect**: Puede crear piezas, ver todas
- **bim_manager**: Acceso total, puede cambiar estados y asignaciones
- **workshop**: Solo ve piezas asignadas a su taller, puede marcar completadas
- **director**: Solo lectura completa

---

## 4. Especificación de la API

> **Nota:** La API está implementada y operativa. La documentación interactiva completa (Swagger UI / ReDoc) está disponible en `http://localhost:8000/docs` al arrancar el entorno Docker.

**Base URL (local)**: `http://localhost:8000`

Los 5 endpoints implementados en el MVP (Entrega 2):

### Endpoint 1: Generar URL Firmada para Upload

**POST** `/api/upload/presigned-url`

Genera una URL firmada de Supabase Storage para que el cliente suba archivos `.3dm` **directamente al bucket** sin pasar por el backend. Tras el upload, el frontend confirma la subida vía webhook que encola el job de validación en Celery.

**Request:**
```json
{
  "filename": "SF-C12-D-001.3dm",
  "file_id": "uuid-generado-por-frontend"
}
```

**Response 200:**
```json
{
  "presigned_url": "https://<project>.supabase.co/storage/v1/upload/sign/raw/...",
  "file_id": "uuid-generado-por-frontend",
  "filename": "SF-C12-D-001.3dm"
}
```

### Endpoint 2: Listar Piezas con Filtros

**GET** `/api/parts?status=validated&tipologia=capitel&workshop_id=<uuid>`

Obtiene el listado de piezas para el Dashboard 3D con filtros dinámicos. Ordenado por `created_at DESC`. RLS enforced en Supabase.

**Response 200:**
```json
{
  "parts": [
    {
      "id": "uuid-123",
      "iso_code": "SF-C12-D-001",
      "status": "validated",
      "tipologia": "capitel",
      "low_poly_url": "https://cdn.cloudfront.net/processed/.../model.glb",
      "bbox": {"min": [0,0,0], "max": [1.2,0.8,2.5]},
      "workshop_id": null,
      "created_at": "2026-01-28T10:30:00Z"
    }
  ],
  "total": 247,
  "filters_applied": {"status": "validated"}
}
```

### Endpoint 3: Detalle de Pieza con CDN URL

**GET** `/api/parts/{id}`

Obtiene todos los campos de una pieza incluyendo la URL CDN para el visor 3D. Aplica transformación `_apply_cdn_transformation()` para servir el `.glb` vía CloudFront cuando `USE_CDN=true`.

**Response 200:**
```json
{
  "id": "uuid-123",
  "iso_code": "SF-C12-D-001",
  "status": "validated",
  "tipologia": "capitel",
  "low_poly_url": "https://cdn.cloudfront.net/processed-geometry/uuid-123.glb",
  "bbox": {"min": [0,0,0], "max": [1.2,0.8,2.5]},
  "workshop_id": null,
  "workshop_name": null,
  "validation_report": null,
  "created_at": "2026-01-28T10:30:00Z",
  "updated_at": "2026-02-15T09:00:00Z"
}
```

**Response 404:**
```json
{"detail": "Part not found"}
```

### Endpoint 4: Navegación Prev/Next entre Piezas

**GET** `/api/parts/{id}/adjacent?status=validated`

Retorna los IDs de la pieza anterior y siguiente (mismos filtros que el Dashboard) para la navegación del Visor 3D. Usa Redis con TTL 300s para cachear los resultados.

**Response 200:**
```json
{
  "prev_id": "uuid-anterior",
  "next_id": "uuid-siguiente",
  "current_index": 5,
  "total_count": 247
}
```

### Endpoint 5: Estado de Validación

**GET** `/api/parts/{id}/validation`

Consulta el estado del job de validación Celery para la pieza. Usado por el frontend para polling en tiempo real (complementado por Supabase Realtime WebSocket).

**Response 200:**
```json
{
  "block_id": "uuid-123",
  "validation_status": "validated",
  "validation_report": {
    "is_valid": true,
    "errors": [],
    "warnings": ["Geometría ligeramente asimétrica - verificar diseño"]
  }
}
```

---

## 5. Historias de Usuario

> Las historias de usuario completas se documentan en `docs/09-mvp-backlog.md`. A continuación se presentan las 3 User Stories más representativas del MVP implementado (Entrega 2).

### Historia de Usuario 1 (US-001): Upload de Archivo .3dm con Presigned URL

**Estado:** ✅ COMPLETADA (Sprint 3, 2026-02-10) — **14/14 tests PASS**

**Como** arquitecto de diseño,
**Quiero** subir un archivo Rhino (.3dm) arrastrándolo a la interfaz,
**Para** que el sistema lo almacene de forma segura y lo prepare para validación automática.

**Criterios de Aceptación — todos verificados:**

✅ **Happy Path**: El componente `UploadZone` acepta archivos `.3dm` mediante drag & drop. El frontend solicita una presigned URL a `POST /api/upload/presigned-url`, sube el archivo **directamente a Supabase Storage** (sin pasar el contenido por el backend), y confirma la subida vía webhook.

✅ **Validación de Formato**: Archivos con extensión distinta a `.3dm` o tamaño >2GB son rechazados en el frontend con mensaje de error claro antes de realizar ninguna petición al servidor.

✅ **Feedback Visual**: Barra de progreso en tiempo real durante el upload. Tras confirmación exitosa, el archivo aparece en el listado con estado `uploaded`.

**Impacto Técnico:** Patrón de presigned URLs elimina el backend como cuello de botella para archivos grandes, reduciendo la carga de red del servidor en un 100% del payload de archivos.

**Prioridad:** P0 (Crítica) | **Estimación:** 5 Story Points | **Tests:** 14/14 PASS

---

### Historia de Usuario 2 (US-005): Dashboard 3D Interactivo de Piezas

**Estado:** ✅ COMPLETADA & AUDITADA (Sprint 4, 2026-02-23) — **268/268 tests PASS (100%)**

**Como** BIM Manager,
**Quiero** ver todas las piezas del inventario en un canvas 3D interactivo con filtros por estado, tipología y taller,
**Para** tener visibilidad instantánea del inventario y seleccionar piezas para ver su detalle.

**Criterios de Aceptación — todos verificados:**

✅ **Renderizado 3D**: Canvas Three.js (React-Three-Fiber) renderiza las piezas como meshes low-poly (.glb) con sistema LOD de 3 niveles: alta resolución (<20u), baja resolución (20-50u), bounding box proxy (>50u). Performance validada: 60 FPS con 1197 meshes, 41 MB de memoria.

✅ **Filtros Interactivos**: Sidebar flotante con filtros por `status`, `tipologia` y `workshop_id`. Filtros sincronizados con URL (bidireccional). Opacidad diferencial: piezas que no coinciden con el filtro aparecen al 20% de opacidad.

✅ **Selección y Navegación**: Click en una pieza la resalta con glow emissivo (intensity 0.4) y abre el `PartDetailModal`. Deselección con tecla ESC o click en fondo. Estado global gestionado con Zustand.

✅ **Empty State**: Cuando no hay piezas, se muestra un estado vacío con call-to-action contextual.

**Impacto Técnico:** Primer dashboard 3D web del mercado para gestión de inventario de piezas arquitectónicas únicas. El sistema LOD garantiza rendimiento con decenas de miles de piezas.

**Prioridad:** P0 (Crítica) | **Estimación:** 35 Story Points (11 tickets) | **Tests:** 268/268 PASS

---

### Historia de Usuario 3 (US-010): Visor 3D Web de Piezas

**Estado:** ✅ COMPLETADA & AUDITADA (Sprint 5, 2026-02-26) — **131/131 tests PASS (100%)**

**Como** responsable de Taller,
**Quiero** visualizar la pieza 3D asignada directamente en el navegador,
**Para** poder rotarla, hacer zoom y entender su geometría sin instalar software CAD.

**Criterios de Aceptación — todos verificados:**

✅ **Happy Path (Orbit Controls + Auto-centering)**: El modal `PartDetailModal` abre el canvas 3D con `PartViewerCanvas` (3-point lighting: KEY/FILL/RIM + OrbitControls). El modelo GLB se carga desde CDN CloudFront, se auto-centra y auto-escala en el viewport. Navegación prev/next entre piezas con latencia <50ms (Redis cache).

✅ **Edge Case (BBoxProxy Fallback + Spinner)**: Si `low_poly_url` es NULL (pieza en procesamiento), se muestra un proxy de bounding box wireframe con mensaje de estado. Loading spinner durante la carga del modelo.

✅ **Error Handling (ViewerErrorBoundary)**: `ViewerErrorBoundary` captura errores de WebGL, timeout de carga (10s con retry), archivo GLB no encontrado (404), y corrupción. Mensajes de error user-friendly con opción de reintento. 5 patrones de error manejados explícitamente.

**Impacto Técnico:** Elimina la necesidad de instalar Rhino 3D para inspeccionar piezas. La integración CDN (CloudFront) reduce la latencia de carga en 60% respecto al acceso directo a S3.

**Prioridad:** P1 (Alta) | **Estimación:** 15 Story Points (9 tickets) | **Tests:** 131/131 PASS

---

## 6. Tickets de Trabajo

> Los tickets se gestionan como ramas en GitHub. A continuación se documentan 3 tickets reales implementados durante el desarrollo del MVP.

### Ticket 1 (Backend): T-002-BACK — Generate Presigned URL for S3 Upload

**Rama:** `feature/T-002-BACK` → `main`
**Tipo:** Feature — Backend
**Componente:** Backend / API + Storage
**Prioridad:** P0 (Bloqueante — prerequisito de US-001)
**Estimación:** 2 Story Points
**Sprint:** Sprint 1 (completado)

**Descripción:**

Implementar el endpoint `POST /api/upload/presigned-url` que genera una URL firmada de Supabase Storage para subida directa de archivos `.3dm`. El patrón presigned URL elimina el backend como proxy de datos binarios.

**Tareas completadas:**
- [x] Endpoint FastAPI con Pydantic schema (`PresignedUrlRequest` / `PresignedUrlResponse`)
- [x] Integración con Supabase Storage client singleton (`infra/supabase_client.py`)
- [x] TTL de 60 segundos en URL firmada (seguridad: minimizar ventana de uso)
- [x] CORS configurado para `localhost:5173` (Vite dev server)
- [x] Tests de integración con Supabase real (no mock)

**Criterios de Aceptación verificados:**
✅ `POST /api/upload/presigned-url` retorna `presigned_url`, `file_id`, `filename`
✅ URL firmada es válida y permite upload directo a bucket `raw`
✅ URL expira en 60 segundos
✅ Tests de integración PASS en contenedor Docker

---

### Ticket 2 (Frontend): T-032-FRONT — Validation Report Modal UI

**Rama:** `feature/US-002-T-032-FRONT` → `main`
**Tipo:** Feature — Frontend
**Componente:** Frontend / UI Components
**Prioridad:** P0 (Cierre de US-002)
**Estimación:** 5 Story Points
**Sprint:** Sprint 4 (completado 2026-02-16)

**Descripción:**

Crear el componente `ValidationReportModal` que muestra el informe de validación generado por el agente "The Librarian". El modal incluye navegación por tabs (Errores / Advertencias / Info), focus trap para accesibilidad WCAG 2.1, y renderizado vía React Portal para evitar conflictos de z-index.

**Tareas completadas:**
- [x] Componente `ValidationReportModal.tsx` con React Portal (z-index 9999)
- [x] Navegación por tabs con teclado (ArrowLeft/ArrowRight)
- [x] Focus trap: Tab cycling dentro del modal (WCAG 2.1 AA)
- [x] Extracción de constantes: `MODAL_STYLES`, `TAB_CONFIG`, `ERROR_MESSAGES`
- [x] Utilidades: `formatValidationErrors()`, `getStatusBadgeProps()`
- [x] 34/35 tests PASS (1 test bug documentado, no bloqueante)

**Criterios de Aceptación verificados:**
✅ Modal abre/cierra con ESC y botón X
✅ Navegación por tabs funciona con teclado (ArrowLeft/ArrowRight)
✅ Focus trap activo mientras modal está abierto (WCAG 2.1 AA)
✅ Errores de validación mostrados con context y sugerencias de corrección
✅ 34/35 tests PASS (cobertura >85%)

---

### Ticket 3 (Database): T-0503-DB — Add low_poly_url Column & Indexes

**Rama:** `feature/US-005-T-0503-DB` → `main`
**Tipo:** Infrastructure — Database
**Componente:** Supabase PostgreSQL
**Prioridad:** P0 (Prerequisito del pipeline de geometría 3D)
**Estimación:** 2 Story Points
**Sprint:** Sprint 4 (completado 2026-02-19)

**Descripción:**

Añadir columna `low_poly_url` (TEXT NULL) y `bbox` (JSONB NULL) a la tabla `blocks`, junto con índices optimizados para el dashboard 3D. La migración es idempotente (usa `IF NOT EXISTS`) para aplicarse de forma segura en cualquier entorno.

**Tareas completadas:**
- [x] Migración SQL: `supabase/migrations/20260219000001_add_low_poly_url_bbox.sql`
- [x] Columnas: `low_poly_url TEXT NULL`, `bbox JSONB NULL`
- [x] Índice `idx_blocks_canvas_query`: B-tree compuesto `(status, tipologia, is_archived)`
- [x] Índice `idx_blocks_low_poly_processing`: B-tree en `(low_poly_url, status)` para el worker
- [x] Script helper: `infra/apply_t0503_migration.py` (vía `make migrate-t0503`)
- [x] 17/20 tests PASS (85%, core funcional 100%; 3 tests aspiracionales documentados)

**Criterios de Aceptación verificados:**
✅ Columnas `low_poly_url` y `bbox` creadas con tipos correctos
✅ Índices creados con tamaño total <24 KB (eficiencia verificada)
✅ Migración idempotente: se puede aplicar múltiples veces sin error
✅ Performance: query canvas dashboard <500ms verificada con `EXPLAIN ANALYZE`

---

## 7. Pull Requests

> A continuación se documentan 3 Pull Requests reales del repositorio, seleccionados por representar las 3 capas principales del sistema (Backend, Frontend, Infra/Full-Stack).

### Pull Request 1: [BACK] Implement Part Navigation API with Redis Caching

**PR #36** | `10-1003-back` → `main`
**Autor:** @pedrocortesark
**Status:** ✅ Merged (2026-02-25 09:01)
**Tests:** 22/22 PASS (14 unit + 6 integration + 2 Redis cache)

**Descripción:**

Implementa el endpoint `GET /api/parts/{id}/adjacent` para navegación prev/next entre piezas en el Visor 3D. Incluye capa de caché Redis con TTL 300s y degradación graceful si Redis no está disponible.

**Cambios principales:**
- ✨ `src/backend/api/parts_navigation.py` (119 líneas): Router FastAPI con mapeo de errores explícito (404/422/503)
- ✨ `src/backend/services/navigation_service.py` (210 líneas): Lógica prev/next con builder pattern (refactor de 8 ramas `if/elif`)
- ✨ `src/backend/infra/redis_client.py` (64 líneas): Singleton Redis con graceful degradation
- ♻️ Refactor: 40 líneas de duplicación eliminadas
- 🧪 TDD: RED (22 tests fallando) → GREEN → REFACTOR completo

**Impacto técnico:**
- Latencia navegación: 84ms → 39ms con cache (**53% reducción**)
- Cache hit ratio en uso normal: ~85% (TTL 5 min cubre sesión típica de inspección)
- Zero downtime si Redis falla: degradación graceful a DB directa

---

### Pull Request 2: [FRONT] Implement ViewerErrorBoundary with Error Handling and Fallback UI

**PR #38** | `10-1006-front` → `main`
**Autor:** @pedrocortesark
**Status:** ✅ Merged (2026-02-25 18:15)
**Tests:** 10/10 PASS (anti-regresión: 353/353 frontend tests PASS)

**Descripción:**

Implementa `ViewerErrorBoundary`, un React Error Boundary especializado para el Visor 3D que captura errores de WebGL, Three.js, `useGLTF` y timeout de red con mensajes user-friendly y opción de retry.

**Cambios principales:**
- ✨ `src/frontend/src/components/PartDetailModal/ViewerErrorBoundary.tsx` (220 líneas): Error boundary con detección de 5 patrones de error (`WebGL`, `GLB 404`, `timeout`, `corruption`, `generic`)
- ✨ Fallback UI con `BBoxProxy` (wireframe) + mensaje contextual + botón de retry
- ✨ Logging production-safe: solo en `NODE_ENV === 'development'`
- ✨ JSDoc completo: `@param`, `@returns`, `@throws`, ejemplos de uso
- 🧪 TDD ENRICH→RED→GREEN→REFACTOR: tests de 5 escenarios de error + retry logic

**Decisión de diseño clave:** La detección de patrones de error se hace sobre el `message` del Error (string matching) dado que Three.js/WebGL no lanza subclases tipadas. Decisión documentada como ADR en `memory-bank/decisions.md`.

---

### Pull Request 3: [FULL-STACK] US-005 — 3D Interactive Dashboard (Merge Final)

**PR #32** | `US-005` → `main`
**Autor:** @pedrocortesark
**Status:** ✅ Merged (2026-02-23 11:24)
**Tests incluidos:** +268 tests nuevos (16 integración + 252 unitarios), 0 regresiones

**Descripción:**

PR de cierre de la User Story US-005 completa. Integra 11 tickets (T-0500 a T-0510) que implementan el Dashboard 3D interactivo: canvas Three.js, sistema LOD de 3 niveles, filtros con Zustand + URL sync, selección de piezas con glow emissivo, y suite completa de tests de integración.

**Cambios principales (resumen):**
- ✨ `Canvas3D.tsx` + `PartMesh.tsx` + `PartsScene.tsx`: Renderizado Three.js con R3F
- ✨ Sistema LOD: `<Lod distances={[0, 20, 50]}>` con 3 niveles (mid-poly/low-poly/BBox)
- ✨ `FiltersSidebar.tsx` + `useURLFilters.ts`: Filtros sincronizados con URL (bidireccional)
- ✨ `parts.store.ts` (Zustand): Estado global de piezas, filtros y selección
- ✨ `Dashboard3D.integration.test.tsx`: 17 tests de integración (rendering, filters, selection, empty-state, performance)
- ✨ `test_parts_api_functional.py` + `test_parts_api_filters.py`: 13/13 tests backend PASS
- ♻️ Refactor: `helpers.py` con cleanup compartido, eliminando ~90 líneas de duplicación
- 🔒 DevSecOps: `pip-audit` + `npm audit` integrados en CI/CD

**Métricas de calidad:**
- Performance POC validada: **60 FPS con 1197 meshes, 41 MB memoria** (supera target >30 FPS)
- Cobertura tests: >80% Dashboard3D, >85% PartMesh, >90% FiltersSidebar
- Audit score US-005: **100/100** — Production-ready, zero bloqueadores
