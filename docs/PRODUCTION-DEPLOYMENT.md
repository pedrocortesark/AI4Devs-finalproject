# 🚀 Plan de Deployment a Producción - SF Parts Manager

**Documento**: Guía de Deployment a Producción  
**Versión**: 1.0  
**Fecha**: 2026-02-24  
**Autor**: DevOps Team - AI4Devs  
**Estado Proyecto**: CI/CD ✅ | Tests 100% ✅ | Ready for Production 🚀

---

## 📋 Tabla de Contenidos

1. [Pre-requisitos y Validaciones](#pre-requisitos)
2. [Arquitectura de Producción](#arquitectura)
3. [Variables de Entorno por Servicio](#variables-entorno)
4. [Paso 1: Deployment del Backend (Railway)](#deployment-backend)
5. [Paso 2: Deployment del Frontend (Vercel)](#deployment-frontend)
6. [Paso 3: Configuración de Supabase Producción](#supabase-produccion)
7. [Paso 4: Configuración de Redis Cloud](#redis-cloud)
8. [Paso 5: Celery Workers (Railway)](#celery-workers)
9. [Pipeline de CI/CD Automático](#cicd-pipeline)
10. [Monitoreo y Observabilidad](#monitoreo)
11. [Estrategia de Rollback](#rollback)
12. [Security Hardening](#security)
13. [Testing Post-Deployment](#testing)
14. [Troubleshooting](#troubleshooting)
15. [Cost Management](#cost-management)

---

## 1. Pre-requisitos y Validaciones {#pre-requisitos}

### ✅ Checklist de Pre-Deployment

**Validación de Código:**
```bash
# 1. Verificar que CI/CD pasa
git pull origin main
# Verificar en: https://github.com/[tu-usuario]/AI4Devs-finalproject/actions
# Debe mostrar: ✅ All checks passed

# 2. Verificar tests localmente
make test           # Backend: 7/7 tests passing
make test-front     # Frontend: 4/4 tests passing

# 3. Verificar Docker builds de producción
docker build --target prod -t sf-pm-backend:prod --file src/backend/Dockerfile src/backend
docker build --target prod -t sf-pm-frontend:prod --file src/frontend/Dockerfile src/frontend
# Ambos deben compilar sin errores

# 4. Verificar que no hay secretos expuestos
git log --all --full-history -- "*" | grep -iE "(password|secret|token|key.*=)"
# No debe retornar matches (o solo placeholders)
```

**Cuentas y Servicios Necesarios:**
- ✅ Cuenta Railway (https://railway.app)
- ✅ Cuenta Vercel (https://vercel.com)
- ✅ Supabase Pro Plan activado ($25/mes) (https://supabase.com)
- ✅ Redis Cloud Free Tier (https://redis.com/try-free/)
- ✅ Sentry Free Tier (opcional pero recomendado) (https://sentry.io)
- ✅ GitHub repository con permisos admin

---

## 2. Arquitectura de Producción {#arquitectura}

```
┌─────────────────────────────────────────────────────────────┐
│                      INTERNET (HTTPS)                       │
└───────┬─────────────────────────────────────────────┬───────┘
        │                                             │
        │ DNS: sfpm.your-domain.com                  │ DNS: api.sfpm.your-domain.com
        │                                             │
┌───────▼──────────┐                         ┌────────▼────────────┐
│   VERCEL CDN     │                         │   RAILWAY PLATFORM   │
│   (Frontend)     │◄────────API Calls──────►│   (Backend + Workers)│
│                  │                         │                      │
│ • React 18 SPA   │                         │ • FastAPI + Uvicorn │
│ • Vite Build     │                         │ • Celery Workers (×2)│
│ • Static Assets  │                         │ • Redis (Message Q)  │
│ • Auto CDN       │                         │ • Healthcheck: /ready│
└──────────────────┘                         └──────┬───────────────┘
                                                     │
                                                     │ PostgreSQL + Storage
                                              ┌──────▼────────────┐
                                              │ SUPABASE CLOUD    │
                                              │ (Data + Storage)  │
                                              │                   │
                                              │ • PostgreSQL 15   │
                                              │ • Storage Buckets │
                                              │ • Auth (JWT)      │
                                              │ • Realtime WS     │
                                              └───────────────────┘
```

**Flujo de Deployment:**
1. Developer → Git push to `main`
2. GitHub Actions → Tests + Build Validation
3. Railway → Auto-deploy Backend (blue-green)
4. Vercel → Auto-deploy Frontend (CDN propagation)
5. Health checks → Monitor endpoints
6. Logs → Sentry + Railway Logs

---

## 3. Variables de Entorno por Servicio {#variables-entorno}

### **Backend (Railway)**

Crear archivo `.env.production` (NO commitearlo):

```bash
# Environment
ENVIRONMENT=production

# Supabase Configuration
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_KEY=YOUR_SERVICE_ROLE_KEY_HERE
SUPABASE_DATABASE_URL=postgresql://postgres.YOUR_PROJECT_REF:YOUR_DB_PASSWORD@aws-0-REGION.pooler.supabase.com:6543/postgres?sslmode=require

# CORS (Production domain only)
ALLOWED_ORIGINS=https://sfpm.your-domain.com

# Redis Cloud Connection
REDIS_PASSWORD=YOUR_REDIS_CLOUD_PASSWORD
CELERY_BROKER_URL=redis://:YOUR_REDIS_CLOUD_PASSWORD@redis-12345.c1.us-east-1-1.ec2.cloud.redislabs.com:12345/0
CELERY_RESULT_BACKEND=redis://:YOUR_REDIS_CLOUD_PASSWORD@redis-12345.c1.us-east-1-1.ec2.cloud.redislabs.com:12345/0

# Security (generar con: openssl rand -base64 32)
DATABASE_PASSWORD=YOUR_SECURE_PRODUCTION_PASSWORD

# Monitoring (opcional)
SENTRY_DSN=https://YOUR_SENTRY_DSN@sentry.io/YOUR_PROJECT_ID
```

### **Frontend (Vercel)**

Variables de entorno en Vercel Dashboard (Settings → Environment Variables):

```bash
# API Configuration
VITE_API_URL=https://api.sfpm.your-domain.com

# Feature Flags (opcional)
VITE_ENABLE_3D_VIEWER=true
VITE_ENABLE_EXPERIMENTAL_FEATURES=false

# Monitoring (opcional)
VITE_SENTRY_DSN=https://YOUR_FRONTEND_SENTRY_DSN@sentry.io/YOUR_PROJECT_ID
```

---

## 4. Paso 1: Deployment del Backend (Railway) {#deployment-backend}

### 4.1. Crear Proyecto en Railway

```bash
# Instalar Railway CLI
npm install -g @railway/cli

# Login
railway login

# Crear nuevo proyecto
railway init
# Seleccionar: "Create new project"
# Nombre: "sf-pm-backend-prod"

# Link con GitHub repo
railway link
# Seleccionar tu repositorio
```

### 4.2. Configurar Servicio Backend

**En Railway Dashboard (https://railway.app/dashboard):**

1. **New Service** → "GitHub Repo"
2. **Select Repository**: `AI4Devs-finalproject`
3. **Root Directory**: `/src/backend`
4. **Build Settings**:
   ```yaml
   Build Command: pip install -r requirements.txt
   Start Command: uvicorn main:app --host 0.0.0.0 --port $PORT
   Dockerfile Path: src/backend/Dockerfile
   Build Method: Dockerfile
   ```

5. **Environment Variables** (Settings → Variables):
   Copiar todas las variables del archivo `.env.production` (Backend section)

6. **Healthcheck Configuration**:
   ```yaml
   Path: /ready
   Interval: 30s
   Timeout: 5s
   Retries: 3
   ```

7. **Domain Configuration**:
   - Settings → Networking → "Generate Domain"
   - O configurar custom domain: `api.sfpm.your-domain.com`

### 4.3. Desplegar

```bash
# Deployar usando Railway CLI
railway up

# Verificar deployment
railway status

# Ver logs en tiempo real
railway logs

# Verificar health endpoint
curl https://YOUR_RAILWAY_DOMAIN.up.railway.app/ready
# Esperado: {"status":"ok","service":"sagrada-familia-backend"}
```

### 4.4. Configurar Auto-Deploy

**En Railway Dashboard:**
1. Settings → "Deploy Triggers"
2. Activar: "Auto-deploy on push to main"
3. Branch: `main`
4. Path Filter: `src/backend/**`

---

## 5. Paso 2: Deployment del Frontend (Vercel) {#deployment-frontend}

### 5.1. Conectar Repositorio a Vercel

```bash
# Instalar Vercel CLI
npm install -g vercel

# Login
vercel login

# Link proyecto
cd src/frontend
vercel link

# Deploy a producción
vercel --prod
```

### 5.2. Configuración Avanzada en Vercel Dashboard

**Framework Preset**: Vite  
**Root Directory**: `src/frontend`  
**Build Command**: `npm run build`  
**Output Directory**: `dist`  
**Install Command**: `npm ci --omit=dev`

**Variables de Entorno** (Settings → Environment Variables):
- `VITE_API_URL` = `https://api.sfpm.your-domain.com`
- Scope: Production

**Domain Configuration**:
- Domains → Add: `sfpm.your-domain.com`
- Configurar DNS:
  ```
  Type: CNAME
  Name: sfpm
  Value: cname.vercel-dns.com
  ```

### 5.3. Configurar Redirects y Headers

Crear `src/frontend/vercel.json`:

```json
{
  "rewrites": [
    { "source": "/(.*)", "destination": "/index.html" }
  ],
  "headers": [
    {
      "source": "/(.*)",
      "headers": [
        {
          "key": "X-Content-Type-Options",
          "value": "nosniff"
        },
        {
          "key": "X-Frame-Options",
          "value": "DENY"
        },
        {
          "key": "X-XSS-Protection",
          "value": "1; mode=block"
        },
        {
          "key": "Referrer-Policy",
          "value": "strict-origin-when-cross-origin"
        }
      ]
    }
  ]
}
```

### 5.4. Verificar Deployment

```bash
# Verificar build local primero
cd src/frontend
npm run build
npm run preview

# Deployar a producción
vercel --prod

# Acceder a: https://sfpm.your-domain.com
# Verificar que carga correctamente
```

---

## 6. Paso 3: Configuración de Supabase Producción {#supabase-produccion}

### 6.1. Upgrade a Plan Pro

**Dashboard de Supabase** (https://supabase.com/dashboard):
1. Select Project → Settings → Billing
2. Upgrade to **Pro Plan** ($25/mes)
   - 8 GB RAM PostgreSQL (necesario para RLS + queries complejas)
   - 100 GB Storage incluido
   - Daily Backups con point-in-time recovery

### 6.2. Configurar Production Database

**Ejecutar Migraciones:**

```bash
# 1. Conectar a Supabase Production Database
export SUPABASE_DATABASE_URL="postgresql://postgres.XXX:PASSWORD@aws-0-region.pooler.supabase.com:6543/postgres?sslmode=require"

# 2. Ejecutar script de setup (crear tablas)
make setup-events

# 3. Verificar tablas creadas
psql $SUPABASE_DATABASE_URL -c "\dt"
# Esperado: events table visible

# 4. Aplicar migraciones adicionales (si existen)
# (Para futuras migraciones, usar: supabase db push)
```

### 6.3. Configurar Storage Buckets

**En Supabase Dashboard** → Storage:

1. **Crear Buckets**:
   - `raw-uploads` (Private)
   - `processed` (Private)
   - `public-thumbnails` (Public)

2. **Configurar Policies (RLS)**:

```sql
-- Policy: Allow backend service_role to upload
CREATE POLICY "Backend can upload to raw-uploads"
ON storage.objects
FOR INSERT
WITH CHECK (
  bucket_id = 'raw-uploads' 
  AND auth.role() = 'service_role'
);

-- Policy: Allow authenticated users to read
CREATE POLICY "Authenticated users can read processed files"
ON storage.objects
FOR SELECT
USING (
  bucket_id = 'processed' 
  AND auth.role() = 'authenticated'
);
```

3. **Configurar CORS**:
   - Settings → Storage → CORS
   - Allowed Origins: `https://sfpm.your-domain.com`
   - Allowed Methods: `GET, POST, PUT`

### 6.4. Configurar Autenticación (si aplica)

**En Supabase Dashboard** → Authentication:
1. Settings → Auth Providers
2. Configurar email/password authentication
3. Site URL: `https://sfpm.your-domain.com`
4. Redirect URLs: `https://sfpm.your-domain.com/auth/callback`

---

## 7. Paso 4: Configuración de Redis Cloud {#redis-cloud}

### 7.1. Crear Database en Redis Cloud

1. **Signup/Login**: https://redis.com/try-free/
2. **Create Subscription** → Free Tier (30MB)
3. **Create Database**:
   - Name: `sf-pm-celery-prod`
   - Memory: 30 MB
   - Region: US-East-1 (o más cercano a Railway)

4. **Obtener Connection String**:
   ```
   redis://:PASSWORD@redis-12345.c1.us-east-1-1.ec2.cloud.redislabs.com:12345
   ```

5. **Configurar Security**:
   - Access Control → Add Railway IPs to allowlist

### 7.2. Actualizar Variables de Entorno en Railway

```bash
railway variables set CELERY_BROKER_URL="redis://:[PASSWORD]@[REDIS_HOST]:[PORT]/0"
railway variables set CELERY_RESULT_BACKEND="redis://:[PASSWORD]@[REDIS_HOST]:[PORT]/0"
```

---

## 8. Paso 5: Celery Workers (Railway) {#celery-workers}

### 8.1. Crear Servicio Worker en Railway

**En Railway Dashboard:**

1. **New Service** → "GitHub Repo" (mismo repo)
2. **Root Directory**: `/src/backend`
3. **Start Command**:
   ```bash
   celery -A agent.tasks worker --loglevel=info --concurrency=2
   ```

4. **Environment Variables** (compartir con Backend service):
   - Mismo `.env` que el backend
   - Asegurar `CELERY_BROKER_URL` y `CELERY_RESULT_BACKEND` configurados

5. **Recursos**:
   - Memory: 512 MB (suficiente para 2 workers concurrentes)
   - CPU: Shared (Free tier OK)

### 8.2. Verificar Workers

```bash
# Ver logs de workers
railway logs --service celery-worker

# Deberías ver:
# [tasks]
#   . agent.tasks.process_uploaded_file
# celery@worker-1 ready.
```

---

## 9. Pipeline de CI/CD Automático {#cicd-pipeline}

### 9.1. GitHub Actions Workflow Actualizado

Ya tienes `.github/workflows/ci.yml` funcionando. Para producción, añade deployment automático:

Crear `.github/workflows/deploy-production.yml`:

```yaml
name: Production Deployment

on:
  push:
    branches: [main]
  workflow_dispatch:

env:
  DOCKER_BUILDKIT: 1

jobs:
  deploy-backend:
    name: Deploy Backend to Railway
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install Railway CLI
        run: npm install -g @railway/cli

      - name: Deploy to Railway
        run: railway up --service backend
        env:
          RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}

      - name: Wait for Healthcheck
        run: |
          sleep 30
          curl -f ${{ secrets.RAILWAY_BACKEND_URL }}/ready || exit 1

  deploy-frontend:
    name: Deploy Frontend to Vercel
    runs-on: ubuntu-latest
    needs: deploy-backend
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Install Vercel CLI
        run: npm install -g vercel

      - name: Deploy to Vercel
        run: vercel --prod --token ${{ secrets.VERCEL_TOKEN }}
        working-directory: src/frontend
```

### 9.2. Configurar Secrets en GitHub

**Settings → Secrets and Variables → Actions:**

```bash
RAILWAY_TOKEN=your_railway_api_token  # Obtener de: railway.app/account/tokens
RAILWAY_BACKEND_URL=https://YOUR_RAILWAY_DOMAIN.up.railway.app
VERCEL_TOKEN=your_vercel_token        # Obtener de: vercel.com/account/tokens
```

---

## 10. Monitoreo y Observabilidad {#monitoreo}

### 10.1. Configurar Sentry

```bash
# Backend
pip install sentry-sdk[fastapi]
```

En `src/backend/main.py`:

```python
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration

if os.getenv("ENVIRONMENT") == "production":
    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.1,
        environment="production"
    )
```

**Frontend:**

```bash
npm install @sentry/react
```

En `src/frontend/src/main.tsx`:

```typescript
import * as Sentry from "@sentry/react";

if (import.meta.env.PROD) {
  Sentry.init({
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: "production",
    tracesSampleRate: 0.1,
  });
}
```

### 10.2. Logging Estructurado

**Backend** (ya configurado con structlog):

```python
import structlog

logger = structlog.get_logger()
logger.info("request_processed", 
           endpoint="/api/upload", 
           status=200, 
           duration_ms=45)
```

**Acceder a logs:**

```bash
# Railway logs (backend + workers)
railway logs

# Vercel logs (frontend)
vercel logs

# Supabase logs (database queries)
# Dashboard → Logs → Query Performance
```

### 10.3. Dashboards de Monitoreo

**Railway Dashboard** (https://railway.app/dashboard):
- CPU Usage
- Memory Usage
- Network Traffic
- Request Rate

**Vercel Analytics** (https://vercel.com/analytics):
- Page Load Times
- Core Web Vitals
- Traffic by Region

**Supabase Dashboard** (https://supabase.com/dashboard):
- Database Connections
- Query Performance
- Storage Usage
- API Rate Limits

---

## 11. Estrategia de Rollback {#rollback}

### 11.1. Rollback de Backend (Railway)

```bash
# Ver deployments recientes
railway status --service backend

# Rollback al deployment anterior
railway rollback --service backend

# O rollback a deployment específico
railway rollback --service backend --deployment DEPLOYMENT_ID
```

### 11.2. Rollback de Frontend (Vercel)

```bash
# Ver deployments
vercel ls

# Rollback a deployment anterior
vercel rollback https://sfpm-abc123.vercel.app
```

### 11.3. Rollback de Database Migrations

```bash
# Si la migración causó problemas, revertir manualmente:
psql $SUPABASE_DATABASE_URL

# Ejemplo: Eliminar columna añadida
ALTER TABLE events DROP COLUMN IF EXISTS new_problematic_column;
```

### 11.4. Procedimiento de Emergencia

**Si el sistema está completamente caído:**

1. **Verificar Status Pages**:
   - Railway: https://railway.app/status
   - Vercel: https://vercel-status.com
   - Supabase: https://status.supabase.com

2. **Rollback automático si health check falla**:
   Railway y Vercel tienen rollback automático configurado si el healthcheck falla.

3. **Contacto de Emergencia**:
   - Tech Lead: [tu-email@example.com]
   - DevOps: [devops@example.com]

---

## 12. Security Hardening {#security}

### 12.1. HTTPS Obligatorio

**Backend (Railway)**:
- Redirigir HTTP → HTTPS automático (Railway lo maneja)

**Frontend (Vercel)**:
- HTTPS por defecto (Vercel lo maneja)

### 12.2. CORS Configuration

En `src/backend/config.py`:

```python
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",")

# En main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # ["https://sfpm.your-domain.com"]
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
```

### 12.3. Supabase RLS Enforcement

Verificar que TODAS las tablas tienen RLS habilitado:

```sql
-- Verificar RLS
SELECT tablename, rowsecurity 
FROM pg_tables 
WHERE schemaname = 'public';

-- Habilitar si falta
ALTER TABLE events ENABLE ROW LEVEL SECURITY;
ALTER TABLE blocks ENABLE ROW LEVEL SECURITY;
```

### 12.4. Rate Limiting

Instalar en backend:

```bash
pip install slowapi
```

En `src/backend/main.py`:

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.post("/api/upload/url")
@limiter.limit("10/minute")  # Máximo 10 uploads por minuto
async def upload_url(request: Request):
    ...
```

### 12.5. Secrets Rotation

**Calendario de Rotación:**
- Database Passwords: Cada 90 días
- Supabase Service Key: Cada 180 días
- Redis Password: Cada 90 días
- JWT Secrets: Cada 180 días

**Procedimiento:**
1. Generar nuevo secret
2. Actualizar en Railway/Vercel variables
3. Deploy nuevo build
4. Verificar funcionamiento
5. Invalidar secret anterior

---

## 13. Testing Post-Deployment {#testing}

### 13.1. Smoke Tests Checklist

```bash
# 1. Health Endpoints
curl https://api.sfpm.your-domain.com/ready
# Esperado: {"status":"ok",...}

# 2. Frontend Load
curl -I https://sfpm.your-domain.com
# Esperado: 200 OK

# 3. Database Connectivity
# (Verificar en Railway logs que no hay errores de conexión)

# 4. Storage Access
# (Verificar en Supabase Dashboard: Storage → Files → Upload test file)

# 5. Celery Workers
# (Verificar en Railway logs de worker: "celery@worker-1 ready")

# 6. End-to-End Test Flow (manual):
# - Acceder a https://sfpm.your-domain.com
# - Upload un archivo .3dm de prueba
# - Verificar que aparece en dashboard
# - Verificar logs en Sentry (0 errores esperados)
```

### 13.2. Performance Tests

```bash
# Load test con Apache Bench
ab -n 1000 -c 10 https://api.sfpm.your-domain.com/ready
# Esperado: >200 requests/second

# Frontend bundle size analysis
cd src/frontend
npm run build
npx vite-bundle-visualizer dist/stats.html
# Verificar: main bundle < 500KB gzipped
```

---

## 14. Troubleshooting {#troubleshooting}

### 14.1. Backend no responde

```bash
# 1. Verificar Railway service status
railway status

# 2. Ver logs recientes
railway logs --follow

# 3. Verificar variables de entorno
railway variables

# 4. Verificar health endpoint
curl https://YOUR_RAILWAY_DOMAIN.up.railway.app/ready

# 5. Reiniciar servicio si es necesario
railway restart --service backend
```

### 14.2. Frontend muestra errores 404 en API calls

**Causas comunes:**
1. `VITE_API_URL` mal configurada en Vercel
2. CORS bloqueando requests

**Solución:**
```bash
# Verificar variables en Vercel
vercel env ls

# Ver logs del navegador (DevTools → Console)
# Buscar: "CORS error" o "Failed to fetch"

# Verificar CORS en backend logs
railway logs | grep CORS
```

### 14.3. Celery workers no procesan tareas

```bash
# 1. Verificar worker logs
railway logs --service celery-worker

# 2. Verificar conexión Redis
redis-cli -u $CELERY_BROKER_URL ping
# Esperado: PONG

# 3. Verificar tareas pendientes
redis-cli -u $CELERY_BROKER_URL llen celery
# Número de tareas en cola

# 4. Reiniciar workers
railway restart --service celery-worker
```

### 14.4. Database slow queries

**En Supabase Dashboard:**
1. Logs → Query Performance
2. Identificar queries lentas (> 1s)
3. Añadir índices si es necesario:

```sql
CREATE INDEX IF NOT EXISTS idx_events_created_at 
ON events(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_blocks_status 
ON blocks(status);
```

---

## 15. Cost Management {#cost-management}

### 15.1. Costos Mensuales Estimados

| Servicio | Tier | Costo/Mes | Recursos |
|----------|------|-----------|----------|
| **Railway Backend** | Starter | $10 | 512MB RAM, Shared CPU |
| **Railway Workers** | Starter | $10 | 512MB RAM, 2 workers |
| **Vercel Frontend** | Hobby | $0 | 100GB bandwidth |
| **Supabase** | Pro | $25 | 8GB DB, 100GB storage |
| **Redis Cloud** | Free | $0 | 30MB |
| **Sentry** | Developer | $0 | 5k events/month |
| **TOTAL MVP** | | **$45/mes** | |

**Escalabilidad (100+ usuarios activos):**
- Railway: $20/mes (1GB RAM)
- Vercel Pro: $20/mes (Enterprise analytics)
- Supabase Pro: $100/mes (4GB DB, 500GB storage)
- Redis Cloud: $10/mes (100MB)
- **Total Producción:** ~$150/mes

### 15.2. Optimización de Costos

**Tips:**
1. **Railway**: Activar sleep mode para workers en horarios sin actividad
2. **Vercel**: Comprimir assets con Brotli (ya configurado)
3. **Supabase**: Configurar retention policy (eliminar logs > 7 días)
4. **Redis**: Usar TTL en cache keys (expiración automática)

---

## 🎉 Deployment Completado

**Checklist Final:**
- ✅ Backend deployed a Railway con healthcheck funcionando
- ✅ Frontend deployed a Vercel con custom domain
- ✅ Supabase Production configurado con RLS
- ✅ Redis Cloud conectado y workers activos
- ✅ CI/CD pipeline automático configurado
- ✅ Monitoring con Sentry funcionando
- ✅ Smoke tests pasando 100%
- ✅ Documentación de rollback disponible
- ✅ Security hardening aplicado

**URLs de Producción:**
- Frontend: https://sfpm.your-domain.com
- Backend API: https://api.sfpm.your-domain.com
- Health Check: https://api.sfpm.your-domain.com/ready
- Sentry Dashboard: https://sentry.io/organizations/[your-org]/projects/

**Próximos Pasos:**
1. Configurar alertas en Sentry (errores > 10/hour)
2. Configurar backups automáticos de Supabase (ya incluido en Pro plan)
3. Implementar feature flags para A/B testing
4. Monitorear costos semanalmente

---

**Contacto de Soporte:**
- Tech Lead: [tu-email]
- DevOps: [devops-email]
- Documentación: [Confluence/Notion link]

---

**Última actualización**: 2026-02-24  
**Versión**: 1.0 (Production Ready)  
**Mantenido por**: DevOps Team - AI4Devs
