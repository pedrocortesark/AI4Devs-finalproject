# Runbook de Despliegue — SF-PM en Producción

**Fecha:** 2026-02-27 | **Plataforma:** Railway + Vercel + Supabase

Este documento son los pasos manuales ordenados para llevar SF-PM de local a producción.
Ejecutar en el orden indicado. Los comandos asumen Git Bash con las variables del `.env` cargadas.

---

## PREREQUISITO: Verificar Builds Docker prod

Antes de desplegar, confirmar que los tres Dockerfiles compilan en target `prod`:

```bash
# Arrancar Docker Desktop primero si no está corriendo

# Backend
docker build --target prod -t sf-pm-backend:prod --file src/backend/Dockerfile src/backend

# Frontend
docker build --target prod -t sf-pm-frontend:prod --file src/frontend/Dockerfile src/frontend

# Agent
docker build --target prod -t sf-pm-agent:prod  --file src/agent/Dockerfile src/agent
```

Todos deben terminar con `Successfully built`. Si falla el agent por `open3d`, verificar que el sistema base tiene las librerías `libx11-6 libgl1 libgomp1`.

---

## PASO 1: Aplicar Migraciones a Supabase Cloud ✅ COMPLETADO

Las migraciones se aplican via Docker (no requiere `psql` instalado localmente).

### Comando principal (Git Bash)

```bash
make migrate-cloud
```

El Makefile usa `SHELL := bash` y `MSYS_NO_PATHCONV=1` para evitar problemas de rutas en Windows.
Requiere que `SUPABASE_DATABASE_URL` esté configurada en `.env` con la URL del pooler de Supabase.

### Alternativa PowerShell (sin Git Bash)

```powershell
.\scripts\migrate-cloud.ps1
```

### Alternativa: Supabase Dashboard SQL Editor

1. Ir a [supabase.com](https://supabase.com) → tu proyecto → **SQL Editor**
2. Ejecutar en este orden (New Query → pegar → Run):
   - `supabase/migrations/20260207133355_create_raw_uploads_bucket.sql`
   - `supabase/migrations/20260211155000_create_blocks_table.sql`
   - `supabase/migrations/20260211160000_add_validation_report.sql`
   - `supabase/migrations/20260212100000_extend_block_status_enum.sql`
   - `supabase/migrations/20260219000001_add_low_poly_url_bbox.sql`

### Verificar

En el Dashboard de Supabase → **Table Editor** deben aparecer: `blocks`, `events`

> Las tablas `zones`, `workshops`, `profiles`, `attachments`, `notifications` son de US futuras y aún no existen.

---

## PASO 2: Inicializar Buckets de Supabase Storage ✅ COMPLETADO

El script `infra/init_db.py` crea los dos buckets necesarios:
- `raw-uploads` — privado (archivos .3dm, acceso via presigned URLs)
- `processed-geometry` — público (archivos .glb para Three.js)

```bash
make init-db
```

El target usa `--no-deps` para **no arrancar la base de datos local** (solo necesita conectarse a Supabase cloud via `SUPABASE_URL` + `SUPABASE_KEY` del `.env`).

```makefile
# Makefile — comando actual
init-db:
    docker compose run --rm --no-deps backend python /app/infra/init_db.py
```

### Verificar

En Supabase Dashboard → **Storage** deben aparecer: `raw-uploads`, `processed-geometry`

---

## PASO 3: Crear Proyecto Railway y añadir Redis

```bash
# Login con GitHub (npx descarga Railway CLI sin instalación global)
npx @railway/cli login

# Crear proyecto vacío
npx @railway/cli init
# Seleccionar: Empty Project
# Nombre: sf-pm

# Nota: Si prefieres instalar globalmente para evitar escribir 'npx @railway/cli':
# npm install -g @railway/cli
# Luego puedes usar solo: railway login, railway init, etc.
```

En el **Railway Dashboard**:
1. Proyecto `sf-pm` → **New** → **Database** → **Add Redis**
2. Railway crea un Redis 7 gestionado
3. La variable `${{Redis.REDIS_URL}}` queda disponible para los servicios del mismo proyecto

---

## PASO 4: Desplegar Backend (FastAPI)

En Railway Dashboard → proyecto `sf-pm` → **New Service** → **GitHub Repo**:

| Campo | Valor |
|---|---|
| Root Directory | `src/backend` |
| Dockerfile Path | `Dockerfile` |
| Docker Build Target | `prod` |
| Service Name | `sf-pm-backend` |

Variables de entorno (**Settings → Variables**):

```
SUPABASE_URL          = https://[TU_PROYECTO].supabase.co
SUPABASE_KEY          = [NUEVA_SERVICE_ROLE_KEY]
DATABASE_URL          = postgresql://postgres:[PASS]@[HOST]:5432/postgres?sslmode=require
CELERY_BROKER_URL     = ${{Redis.REDIS_URL}}
ALLOWED_ORIGINS       = https://sf-pm-frontend.vercel.app
ENVIRONMENT           = production
CDN_BASE_URL          = https://[TU_PROYECTO].supabase.co/storage/v1/object/public/processed-geometry
USE_CDN               = false
```

Railway desplegará automáticamente. Verificar:

```bash
curl https://sf-pm-backend.up.railway.app/health
# Esperado: {"status":"ok"}

curl https://sf-pm-backend.up.railway.app/ready
# Esperado: {"status":"ready","checks":{"database":"ok","redis":"ok"}}
```

---

## PASO 5: Desplegar Agent Worker (Celery)

En Railway Dashboard → **New Service** → **GitHub Repo**:

| Campo | Valor |
|---|---|
| Root Directory | `src/agent` |
| Dockerfile Path | `Dockerfile` |
| Docker Build Target | `prod` |
| Service Name | `sf-pm-agent-worker` |
| Start Command (override) | `celery -A celery_app worker --loglevel=warning --concurrency=4` |

Variables de entorno:

```
SUPABASE_URL            = https://[TU_PROYECTO].supabase.co
SUPABASE_KEY            = [NUEVA_SERVICE_ROLE_KEY]
DATABASE_URL            = postgresql://postgres:[PASS]@[HOST]:5432/postgres?sslmode=require
CELERY_BROKER_URL       = ${{Redis.REDIS_URL}}
CELERY_RESULT_BACKEND   = ${{Redis.REDIS_URL}}
```

Verificar en Railway Logs:
```
celery@[hostname] ready.
```

> El agent-worker no expone puerto HTTP. Railway mostrará "No healthcheck configured" — es correcto.

---

## PASO 6: Desplegar Frontend en Vercel

```bash
# Desde la carpeta del frontend
cd src/frontend

# Primera ejecución: gestiona login + configuración del proyecto + despliega a preview
npx vercel
```

> **Nota:** `npx vercel` ejecuta Vercel CLI sin necesidad de instalación global, evitando problemas de permisos con `npm install -g`. No hay un paso de `vercel login` separado — el login se integra en el flujo de la primera ejecución (abre el navegador para autenticarse con GitHub).

El asistente interactivo de la primera ejecución pregunta:
1. **Set up and deploy?** → `Y`
2. **Which scope?** → Tu cuenta de GitHub
3. **Project name** → `sf-pm-frontend` (o el nombre que prefieras)
4. **In which directory is your code located?** → `./` (estamos en `src/frontend`)
5. **Auto-detected framework** → Vite ✓ — confirmar configuración por defecto

Vercel detecta Vite automáticamente y ejecuta `npm run build`. El `vercel.json` ya está en la carpeta.

El primer `npx vercel` despliega a una **URL de preview** (ej: `sf-pm-frontend-xxx.vercel.app`). No es necesario añadir `--prod` en este paso.

### Añadir variables de entorno

En **Vercel Dashboard → tu proyecto → Settings → Environment Variables**:

```
VITE_SUPABASE_URL      = https://[TU_PROYECTO].supabase.co
VITE_SUPABASE_ANON_KEY = [ANON_KEY — NO usar service_role]
VITE_API_URL           = https://sf-pm-backend.up.railway.app
```

> `VITE_API_URL` debe apuntar a la URL del backend de Railway del Paso 4.
> `VITE_SUPABASE_ANON_KEY` es la clave **anon/public** del dashboard de Supabase, no la service_role.

### Desplegar a producción

Tras añadir las variables, desplegar a producción:
```bash
npx vercel --prod
```

Vercel asigna el dominio de producción (ej: `sf-pm-frontend.vercel.app`) y el alias `*.vercel.app` a este despliegue.

---

## PASO 7: Actualizar ALLOWED_ORIGINS con URL de Vercel

Una vez obtenida la URL de Vercel (ej: `https://sf-pm-frontend.vercel.app`), actualizar en Railway → `sf-pm-backend` → Variables:

```
ALLOWED_ORIGINS = https://sf-pm-frontend.vercel.app
```

Railway redesplegará automáticamente el backend.

---

## PASO 8: Verificación E2E Completa

```bash
# 1. Infraestructura
curl https://sf-pm-backend.up.railway.app/health
curl https://sf-pm-backend.up.railway.app/ready

# 2. CORS (desde CLI)
curl -H "Origin: https://sf-pm-frontend.vercel.app" \
     -H "Access-Control-Request-Method: POST" \
     -X OPTIONS \
     https://sf-pm-backend.up.railway.app/api/upload/url \
     -v 2>&1 | grep -i "access-control"
# Debe mostrar: Access-Control-Allow-Origin: https://sf-pm-frontend.vercel.app

# 3. Flujo completo (browser)
# a) Abrir https://sf-pm-frontend.vercel.app
# b) Subir un archivo .3dm de prueba (< 10MB)
# c) Verificar que la barra de progreso sube
# d) Verificar que aparece "Procesando..." (Celery task en curso)
# e) Verificar que aparece "Validado" (Supabase Realtime notification)
# f) Verificar que la pieza aparece en el Dashboard 3D
```

---

## Resumen de URLs de Producción

| Servicio | URL | Tipo |
|---|---|---|
| Frontend | `https://sf-pm-frontend.vercel.app` | Público |
| Backend API | `https://sf-pm-backend.up.railway.app` | Público |
| Supabase | `https://[proyecto].supabase.co` | Gestionado |
| Redis | Interno Railway | Privado |
| Agent Worker | Sin URL (background) | Privado |

---

## Comandos Útiles Post-Despliegue

> **Nota:** Los comandos asumen Railway CLI disponible. Si usaste `npx` en el PASO 3, reemplaza `railway` por `npx @railway/cli` en cada comando.

```bash
# Ver logs del agent worker
railway logs --service sf-pm-agent-worker --tail 100

# Reiniciar backend sin rebuild
railway redeploy --service sf-pm-backend

# Ver variables de entorno del backend
railway variables --service sf-pm-backend

# Conectar shell al worker (para debug)
railway shell --service sf-pm-agent-worker

# Verificar Redis desde el worker
redis-cli -u $REDIS_URL ping
# Esperado: PONG

# Inspeccionar tasks Celery activos
celery -A celery_app inspect active

# Re-desplegar Vercel frontend
npx vercel --prod
```

---

## Tests Locales (DB local Docker)

Los tests de integración que usan `db_connection` verifican el esquema de la DB local Docker.
El esquema proviene **exclusivamente** de las migraciones SQL — esta es la única fuente de verdad.

### Cómo funciona en entorno local

```
supabase/migrations/*.sql  ←── fuente de verdad del esquema
       │
       ├─ make clean + make up  → auto-aplica en volumen nuevo (docker-entrypoint-initdb.d)
       │
       └─ make migrate-local    → aplica a volumen existente (requiere: make up primero)
```

### Inicializar entorno de tests desde cero

```bash
make clean          # Elimina contenedores + volúmenes
make up             # Arranca PostgreSQL local; auto-aplica las 5 migraciones
make test-unit      # Tests unitarios (no necesitan DB local)
make test-infra     # Tests de integración (DB local + Supabase cloud)
```

### Re-aplicar migraciones a volumen existente

Usar cuando se añade una nueva migración sin querer destruir los datos de desarrollo:

```bash
make up             # Asegurarse de que el contenedor db está corriendo
make migrate-local  # Aplica todas las migraciones via docker compose exec
```

### Tests según dependencias

| Comando | Necesita | No necesita |
|---|---|---|
| `make test-unit` | nada | DB local, Supabase cloud |
| `make test-storage` | Supabase cloud | DB local |
| `make test-infra` | DB local + Supabase cloud | — |

> `test-unit` y `test-storage` usan `--no-deps` en `docker compose run` para evitar
> el error de puerto 5432 cuando la DB local no está corriendo.

---

## Problemas Conocidos y Soluciones

Errores encontrados durante el despliegue inicial y cómo se resolvieron.

### Error: Puerto 5432 no disponible al ejecutar `make init-db`

```
Error response from daemon: ports are not available: exposing port TCP 127.0.0.1:5432
```

**Causa:** `docker compose run` arranca todas las dependencias del servicio, incluyendo `db` (PostgreSQL local), que intenta ocupar el puerto 5432.

**Solución:** `init-db` usa `--no-deps` para no arrancar servicios dependientes. `init_db.py` solo necesita conectarse a Supabase cloud, no a la DB local.

---

### Error: DNS resolution failure en `make migrate-cloud`

```
psql: error: connection to server at "db.tqduceanvyckaztgpcmw.supabase.co" failed: Name does not resolve
```

**Causa:** El host directo de Supabase (`db.[ref].supabase.co`) solo tiene registro DNS IPv6. Docker en Windows usa IPv4 por defecto.

**Solución:** Usar la URL del **Pooler de Supabase** (`aws-1-eu-west-2.pooler.supabase.com:6543`) + añadir `--dns 8.8.8.8` al comando Docker. El pooler es IPv4-compatible y además soporta connection pooling en producción.

---

### Error: Git Bash convierte rutas Unix a rutas Windows

```
docker: invalid reference format: repository name must be lowercase
# o bien: C:/Program Files/Git/migrations/...
```

**Causa:** Git Bash en Windows convierte automáticamente paths que parecen Unix (`/migrations`) a paths Windows (`C:/Program Files/Git/migrations`).

**Solución:** Añadir `MSYS_NO_PATHCONV=1` antes del comando Docker para desactivar la conversión de rutas.

---

### Error: `make` usa cmd.exe en lugar de bash

```
No se esperaba -z en este momento.
```

**Causa:** GnuWin32 `make` usa `cmd.exe` como shell por defecto. Las condicionales `-z` son bash, no cmd.

**Solución:** Añadir al inicio del Makefile:
```makefile
SHELL := bash
.SHELLFLAGS := -euo pipefail -c
```

---

### Error: `SUPABASE_DATABASE_URL` no reconocida desde `.env`

**Causa:** El `.env` usaba `export SUPABASE_DATABASE_URL=...` (sintaxis bash). El Makefile carga las variables sin `export`.

**Solución:** El Makefile usa `$(shell grep ... .env)` para parsear el `.env` manualmente, ignorando el prefijo `export`.

---

### Bucket `processed-geometry` no aparece en Supabase Storage

**Causa:** `infra/init_db.py` solo creaba el bucket `raw-uploads`. Faltaba crear `processed-geometry`.

**Solución:** Se actualizó `init_db.py` para crear ambos buckets:
- `raw-uploads` — privado (presigned URLs para .3dm)
- `processed-geometry` — público (URLs directas para .glb en Three.js)

También se corrigió `constants.py`: `STORAGE_BUCKET_PROCESSED` tenía el valor incorrecto `"processed-files"` → corregido a `"processed-geometry"`.
