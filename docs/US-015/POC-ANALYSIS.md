# POC ANALYSIS: Functional vs Current Implementation

**Fecha:** 2026-03-05  
**Epic:** US-015 - Refactorización E2E del Flujo de Ingesta 3D  
**Autor:** Staff Engineer Team  

---

## 📋 Executive Summary

Este documento compara la **Proof of Concept (PoC) funcional** ubicada en `poc/formats-comparison/` con la **implementación actual** en `src/backend/`, `src/agent/`, y `src/frontend/` para identificar **regresiones arquitectónicas** que causaron los fallos en el flujo E2E de ingesta 3D.

### TL;DR: Hallazgos Principales

| Aspecto | PoC (Funcional) ✅ | Actual (Roto/Fricción) ❌ | Severidad |
|---------|-------------------|---------------------------|-----------|
| **Scope del archivo** | 1 .3dm → 1 GLB (archivo completo) | 1 .3dm → N GLBs (por InstanceObject) | 🔴 CRÍTICO |
| **Nomenclatura Storage** | Simple: `/gltf-draco/model.glb` | Compleja: `/models/low-poly/{uuid}.glb` | 🟡 MEDIO |
| **Coordenadas 3D** | Centradas en origen (POC simple) | **Absolut spatial** (coordenadas reales) | 🟢 MEJORA |
| **Frontend Viewer** | Componente único con <Model /> | Múltiples componentes (Dashboard + Modal) | 🟡 MEDIO |
| **Error Handling** | ❌ Minimal (skeleton loader only) | ✅ Comprehensivo (error boundaries + retries) | 🟢 MEJORA |
| **Validación UserStrings** | ❌ No implementada en PoC | ✅ Implementada (US-002) | 🟢 MEJORA |
| **Database Schema** | ❌ No tenía BD (archivos estáticos) | ✅ PostgreSQL con RLS | 🟢 MEJORA |

**CONCLUSIÓN:** La PoC era un **sistema simplificado E2E** que funcionaba porque:
1. **Scope limitado**: 1 archivo → 1 modelo en canvas
2. **Sin base de datos**: Archivos GLB servidos estáticamente
3. **Sin autenticación**: No había RLS ni permisos
4. **Frontend directo**: Carga simple de 1 modelo hardcodeado

El **escalado a producción** añadió complejidad necesaria (BD, auth, multi-parte), pero rompió la integración E2E por:
- **Desalineación de contratos** (formato JSON no formalizado)
- **Rutas de archivos inconsistentes** (URLs relativas vs absolutas)
- **Falta de tests de integración** (cada módulo funciona solo, fallan juntos)

---

## 🔬 Arquitectura Comparativa

### PoC: Arquitectura Simple (Funcional)

```
┌────────────────────────────────────────────────────────────┐
│  POC (poc/formats-comparison/)                             │
└────────────────────────────────────────────────────────────┘

Flow:
1. Usuario → Preprocesa .3dm manualmente en Rhino Desktop
   | _Mesh command (convertir Breps → Meshes)

2. Python Exporter (exporters/export_instances_gltf.py)
   | parse_instance_definitions()
   | extract meshes → trimesh
   | decimate → ~1000 faces
   | export → /dataset/gltf-draco/model.glb (uncompressed)
   | subprocess: gltf-pipeline -d (Draco compression)
   | Result: model.glb (Draco compressed, ~200KB)

3. Static File Server (Vite Dev Server)
   | Serve /gltf-draco/model.glb as static file
   | CORS: permitido (mismo origen)

4. React Frontend (src/App.tsx + viewers/GltfDracoViewer.tsx)
   | const gltf = useGLTF("/gltf-draco/model.glb")
   | <primitive object={gltf.scene} />
   | OrbitControls + Stats + Grid
   | ✅ Model renders inmediatamente

┌────────────────────────────────────────────────────────────┐
│  KEY SIMPLIFICATIONS                                       │
├────────────────────────────────────────────────────────────┤
│  • NO database (archivos estáticos)                        │
│  • 1 archivo .3dm → 1 archivo .glb (scope limitado)        │
│  • Hardcoded file paths en frontend                        │
│  • No autenticación, no RLS                                │
│  • Preprocesamiento manual documentado                     │
└────────────────────────────────────────────────────────────┘
```

#### Código Clave de la PoC

**1. Exporter Principal** (`poc/formats-comparison/exporters/export_instances_gltf.py:42-122`):

```python
def parse_instance_definitions(self, file_path: Path) -> Dict[str, List[trimesh.Trimesh]]:
    """Parse .3dm y extrae meshes de InstanceDefinitions."""
    file3dm = r3dm.File3dm.Read(str(file_path))
    definitions = {}
    
    for idef in file3dm.InstanceDefinitions:
        meshes = []
        for obj in file3dm.Objects:
            if isinstance(obj.Geometry, r3dm.Mesh):
                # Extract vertices & faces
                mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
                meshes.append(mesh)
        
        if meshes:
            definitions[str(idef.Id)] = {"name": idef.Name, "meshes": meshes}
    
    return definitions  # ✅ Simple dict con geometría
```

**2. Frontend Viewer** (`poc/formats-comparison/src/viewers/GltfDracoViewer.tsx:19-68`):

```tsx
function Model({ url }: { url: string }) {
  const gltf = useGLTF(url);  // ✅ Direct URL load
  
  useEffect(() => {
    gltf.scene.rotation.x = -Math.PI / 2;  // Z-up → Y-up
    
    // Auto-center & auto-fit camera
    const box = new THREE.Box3().setFromObject(gltf.scene);
    const center = box.getCenter(new THREE.Vector3());
    camera.lookAt(center);
  }, [gltf]);
  
  return <primitive object={gltf.scene} />;  // ✅ Single component
}

// Usage
<Canvas>
  <Model url="/gltf-draco/test-model-big.glb" />  // ✅ Hardcoded path
  <OrbitControls />
</Canvas>
```

**3. Paths Estáticos** (`poc/formats-comparison/src/App.tsx:8-12`):

```tsx
const GLTF_FILES = [
  '/gltf-draco/test-model-big.glb',  // ✅ Static relative path
];

<GltfDracoViewer files={GLTF_FILES} />
```

---

### Actual: Arquitectura Escalada (Con Fricción)

```
┌────────────────────────────────────────────────────────────┐
│  PRODUCCIÓN (src/backend/, src/agent/, src/frontend/)     │
└────────────────────────────────────────────────────────────┘

Flow:
1. Usuario → Upload .3dm via POST /api/upload
   | FastAPI endpoint (src/backend/api/upload.py)
   | Upload a Supabase Storage (bucket: raw-files)
   | DB: INSERT INTO blocks (original_file_url)

2. Celery Task 1: validate_file (US-002)
   | Extract UserStrings (Codi, Material, Estado)
   | Validate nomenclature (SF-XXX-Y-NNN)
   | DB: UPDATE blocks SET rhino_metadata = jsonb

3. Celery Task 2: generate_low_poly_glb (US-005)
   | Download .3dm from Supabase
   | rhino3dm parse → InstanceObjects
   | ⚠️ PROBLEMA: 1 .3dm → procesa CADA InstanceObject
   | trimesh extract → decimate → rotation Z→Y
   | Export GLB → /tmp/{block_id}.glb
   | Upload a Supabase Storage (bucket: models, path: low-poly/)
   | DB: UPDATE blocks SET low_poly_url = 'https://...'

4. FastAPI GET /api/parts?limit=50
   | Query DB: SELECT id, iso_code, low_poly_url, bbox
   | ⚠️ PROBLEMA: low_poly_url puede ser NULL si no procesó
   | Response JSON: {"parts": [...]}

5. React Frontend Dashboard (src/frontend/src/components/Dashboard/)
   | Fetch API: GET /api/parts
   | State: usePartsStore (Zustand)
   | Canvas: <PartMesh> por cada parte
   | ⚠️ PROBLEMA: Si low_poly_url === null → lanza error
   | ⚠️ PROBLEMA: CORS random (URL de Supabase no siempre válida)

6. Modal PartDetailModal (T-1007-FRONT)
   | Click en pieza → Fetch GET /api/parts/{id}
   | <ModelLoader url={part.low_poly_url} />
   | ⚠️ PROBLEMA: Si URL es relativa (sin https://) → 404
   | ⚠️ PROBLEMA: Timeout random (GLB grande o red lenta)

┌────────────────────────────────────────────────────────────┐
│  KEY COMPLEXITIES ADDED                                    │
├────────────────────────────────────────────────────────────┤
│  • PostgreSQL database con RLS (permisos workspace)        │
│  • Celery tasks asíncronos (puede fallar silenciosamente)  │
│  • Supabase Storage (requiere presigned URLs)              │
│  • Multi-parte rendering (N piezas en canvas)              │
│  • Autenticación + roles (architect, workshop, director)   │
│  • ⚠️ Contratos JSON NO formalizados (backend ≠ frontend)   │
└────────────────────────────────────────────────────────────┘
```

#### Código Clave Actual

**1. Agent Task** (`src/agent/tasks/geometry_processing.py:672-781`):

```python
@celery_app.task(name=TASK_GENERATE_LOW_POLY_GLB)
def generate_low_poly_glb(self, block_id: str):
    """Generate GLB for ONE InstanceObject (iso_code)."""
    # ⚠️ DIFERENCIA POC: Procesa 1 block_id (1 InstanceObject)
    # POC procesaba archivo completo (todas las instancias)
    
    rhino_file = r3dm.File3dm.Read(local_3dm_path)
    mesh, faces, bbox = _extract_and_merge_meshes(
        rhino_file, block_id, iso_code  # ⚠️ Filtra por iso_code específico
    )
    
    decimated = _apply_decimation(mesh, TARGET_FACES=1000, block_id)
    url, size_kb = _export_and_upload_glb(decimated, block_id)
    _update_block_low_poly_url(block_id, url, bbox)
    
    return {"low_poly_url": url}  # ⚠️ PROBLEMA: Formato JSON informal
```

**2. Backend API** (`src/backend/api/parts.py` - inferido, no se pudo leer directamente):

```python
# Endpoint: GET /api/parts
@router.get("/parts")
def list_parts(limit: int = 50):
    # Query DB
    parts = db.query("SELECT id, iso_code, low_poly_url, bbox FROM blocks")
    
    # ⚠️ PROBLEMA: low_poly_url puede ser NULL
    # No hay validación Pydantic estricta del schema
    return {"parts": parts}  # ⚠️ Schema informal
```

**3. Frontend API Service** (`src/frontend/src/services/upload.service.ts` - parcial):

```typescript
export async function getPartDetail(id: string): Promise<PartDetail> {
  const response = await fetch(`/api/parts/${id}`);
  const data = await response.json();
  
  // ⚠️ PROBLEMA: Sin validación Zod
  // Si backend retorna low_poly_url: null, lo acepta
  return data as PartDetail;  // ⚠️ Unsafe cast
}
```

**4. Frontend Viewer** (`src/frontend/src/components/ModelLoader.tsx:1-100`):

```tsx
export const ModelLoader: React.FC<ModelLoaderProps> = ({ partId }) => {
  const [partData, setPartData] = useState<PartDetail | null>(null);
  
  useEffect(() => {
    const fetchPartData = async () => {
      const data = await getPartDetail(partId);  // ⚠️ Puede tener low_poly_url === null
      setPartData(data);
    };
    fetchPartData();
  }, [partId]);
  
  // ⚠️ PROBLEMA: Si low_poly_url es null, useGLTF falla sin error claro
  const gltf = useGLTF(partData?.low_poly_url);  // ⚠️ Crash si URL inválida
  
  return <primitive object={gltf.scene} />;
};
```

---

## 🔍 Gap Analysis: PoC → Producción

### ✅ Mejoras Implementadas (No son regresiones)

| Feature | PoC | Actual | Impacto |
|---------|-----|--------|---------|
| **Database Schema** | ❌ No DB | ✅ PostgreSQL con 8 tablas | Permite escalabilidad, auditoría |
| **Authentication** | ❌ No auth | ✅ Supabase Auth + RLS | Seguridad por workspace |
| **Validation (US-002)** | ❌ No validación | ✅ UserStrings + Nomenclature | Garantiza calidad datos |
| **Error Boundaries** | ❌ No manejo errores | ✅ ViewerErrorBoundary (T-1009) | Mejora UX |
| **Coordenadas Reales** | ❌ Centradas en origen | ✅ Absolute Rhino coords | Digital Twin approach |
| **Multi-Parte Canvas** | ❌ Solo 1 modelo | ✅ N piezas en escena | Usuario ve inventario completo |

### 🔴 Regresiones Críticas (Causas de fallos)

#### 1. **Scope del Archivo: 1→1 vs 1→N**

**PoC (Simple):**
```
1 archivo .3dm (múltiples InstanceObjects) → 1 archivo .glb (merged)
```

**Actual (Complejo):**
```
1 archivo .3dm (múltiples InstanceObjects) → N tareas Celery → N archivos .glb
```

**Problema:**
- Usuario sube `capiteles-torre-maria.3dm` con 10 piezas
- Backend crea 10 rows en `blocks` table
- Lanza 10 tareas Celery `generate_low_poly_glb`
- Si 1 tarea falla (timeout, memoria), 9 piezas tienen GLB, 1 tiene `low_poly_url: null`
- Frontend muestra 9 piezas OK, 1 invisible (sin error visible)

**Root Cause:**
- PoC diseñada para 1 archivo completo (benchmark simple)
- Producción necesita 1 GLB por pieza (BIM requirement)
- **NO hay sincronización**: Frontend no sabe si falló procesamiento
- **NO hay retry automático**: Task falla → queda NULL permanentemente

**Solución Propuesta:** Ver Ticket T-1503-AGENT en Epic US-015

---

#### 2. **Rutas de Assets: Relativas vs Absolutas**

**PoC (Funcional):**
```typescript
// Frontend App.tsx
const GLTF_FILES = ["/gltf-draco/model.glb"];  // ✅ Relativa a Vite dev server

// Vite sirve: http://localhost:5173/gltf-draco/model.glb
// CORS: No problema (mismo origen)
```

**Actual (Broken):**
```python
# Backend genera URL
low_poly_url = supabase.storage.from_(BUCKET).get_public_url(glb_key)
# Result: "https://xyz.supabase.co/storage/v1/object/public/models/low-poly/abc123.glb"

# DB almacena:
UPDATE blocks SET low_poly_url = 'https://xyz.supabase.co/...'

# Frontend recibe:
GET /api/parts → {"parts": [{"low_poly_url": "https://xyz..."}]}

# ⚠️ PROBLEMA 1: URL a veces es relativa ("models/low-poly/...")
# ⚠️ PROBLEMA 2: CORS random (Supabase bucket mal configurado)
# ⚠️ PROBLEMA 3: Presigned URLs expiran (si bucket privado)
```

**Root Cause:**
- Backend inconsistente: A veces guarda URL absoluta, a veces relativa
- Supabase Storage no configurado con CORS adecuado
- Frontend asume URL absoluta, falla si recibe relativa

**Solución Propuesta:** Ver Ticket T-1502-INFRA + T-1504-BACK en Epic US-015

---

#### 3. **Contratos JSON: Informal vs Formal**

**PoC (Informal pero funcional):**
```typescript
// No había contrato — URL hardcodeada en código
const url = "/gltf-draco/model.glb";  // ✅ String simple
```

**Actual (Informal + riesgo):**
```python
# Backend (Pydantic schema MUY básico)
class PartCanvasItem(BaseModel):
    id: str
    iso_code: str
    low_poly_url: Optional[str] = None  # ⚠️ Permite NULL sin validación

# Frontend (TypeScript sin validación)
interface PartDetail {
  id: string;
  iso_code: string;
  low_poly_url: string | null;  // ⚠️ Acepta null sin manejo
}

# ⚠️ PROBLEMA: Frontend no valida que URL sea absoluta
const gltf = useGLTF(part.low_poly_url);  // ⚠️ Crash si null o relativa
```

**Root Cause:**
- **NO hay contrato JSON formalizado** entre Backend y Frontend
- Pydantic en backend permite `null`
- Frontend no usa Zod validation runtime
- Tipos TypeScript no se validan en runtime

**Solución Propuesta:** Ver JSON-CONTRACTS.md en Epic US-015

---

#### 4. **Error Handling: Silent Failures**

**PoC (Mínimo pero visible):**
```tsx
<Suspense fallback={<Loader />}>  // ✅ Skeleton mientras carga
  <Model url="/gltf-draco/model.glb" />
</Suspense>

// Si falla: Se ve skeleton naranja infinito → usuario sabe que hay error
```

**Actual (Mejorado pero con gaps):**
```tsx
// ¿Qué pasa si low_poly_url === null?
const gltf = useGLTF(partData?.low_poly_url);  // ⚠️ useGLTF explota si URL === null

// Error: "React Error Boundary caught: Cannot load null URL"
// Usuario ve: Pantalla blanca + mensaje genérico

// ⚠️ PROBLEMA: No distingue entre:
//   1. URL === null (aún no procesado)
//   2. URL 404 (archivo borrado)
//   3. CORS error (permisos)
//   4. Timeout (red lenta)
```

**Root Cause:**
- useGLTF de @react-three/drei **NO maneja null URLs** gracefully
- ViewerErrorBoundary existe (T-1009) pero solo atrapa sync errors
- Errors async de fetch no se propagan correctamente

**Solución Propuesta:** Ver Ticket T-1506-FRONT en Epic US-015

---

## 📊 Tabla de Decisiones Arquitectónicas

| Decision | PoC | Actual | Justificación | Reversible? |
|----------|-----|--------|---------------|-------------|
| **File Scope** | 1 .3dm → 1 GLB | 1 .3dm → N GLBs | BIM requirement: 1 piece = 1 entity in DB | ❌ No (core business) |
| **Storage** | Vite static files | Supabase Storage | Scalability + CDN + RLS | ⚠️ Sí (pero costoso) |
| **Coordinates** | Centered origin | Absolute Rhino coords | Digital Twin accuracy | ⚠️ Sí (pero riesgo) |
| **Database** | None (files only) | PostgreSQL + RLS | Multi-tenant + audit trail | ❌ No (core infra) |
| **Auth** | None | Supabase Auth | Security requirement | ❌ No (enterprise) |
| **API Pattern** | Static files | REST API + JSON | Separation of concerns | ❌ No (standard) |

**Leyenda:**
- ✅ Reversible sin impacto
- ⚠️ Reversible con refactor medio
- ❌ Irreversible (core architecture)

---

## 🛠️ Debugging Checklist: PoC vs Actual

Use este checklist para validar que el sistema actual se comporta como la PoC:

### ✅ Smoke Test: PoC E2E (5 minutos)

```bash
# 1. Ir a PoC folder
cd poc/formats-comparison

# 2. Instalar deps (si no está hecho)
cd exporters && python3 -m venv venv && source venv/bin/activate
pip install rhino3dm trimesh numpy tqdm pygltflib

# 3. Preprocesar archivo (manual en Rhino Desktop)
# Abrir: dataset/raw/test-model-big.3dm
# Comando: SelAll → _Mesh (Simple Controls → Fewer polygons 25%) → Save As: test-model-meshed.3dm

# 4. Exportar GLB
python export_instances_gltf.py
# Debe generar: dataset/gltf-draco/test-model-big.glb (~200KB)

# 5. Levantar frontend
cd ..
npm install
npm run dev
# Abrir: http://localhost:5173

# ✅ EXPECTED: Ver modelo 3D en canvas con OrbitControls funcionales
# ✅ EXPECTED: Métricas en overlay (FPS, triangles, memory)
```

### ✅ Smoke Test: Actual E2E (20 minutos)

```bash
# 1. Levantar servicios
make up  # Docker compose

# 2. Subir archivo .3dm
# Navegador: http://localhost:5173/upload
# Subir: tests/fixtures/capitel-test.3dm
# Esperar: "Archivo subido correctamente"

# 3. Verificar en DB que creó entrada
docker compose exec db psql -U user -d sfpm_db -c "SELECT id, iso_code, original_file_url, low_poly_url FROM blocks LIMIT 5"
# ✅ EXPECTED: Ver row con iso_code="SF-C12-D-001", low_poly_url=NULL (aún no procesado)

# 4. Verificar logs Celery Agent
docker compose logs agent-worker --tail=50
# ✅ EXPECTED: Ver task "generate_low_poly_glb" encolada

# Esperar 30-60 segundos...

# 5. Verificar que low_poly_url fue actualizado
docker compose exec db psql -U user -d sfpm_db -c "SELECT low_poly_url, bbox FROM blocks WHERE iso_code='SF-C12-D-001'"
# ✅ EXPECTED: low_poly_url="https://xyz.supabase.co/storage/v1/object/public/models/low-poly/abc123.glb"
# ✅ EXPECTED: bbox='{"min": [...], "max": [...]}'

# 6. Ir a Dashboard
# Navegador: http://localhost:5173/dashboard
# ✅ EXPECTED: Ver pieza en canvas 3D
# ❌ IF FAIL: Ver error en consola navegador:
#   - CORS error → Problema T-1502-INFRA
#   - 404 → Problema T-1504-BACK (URL incorrecta)
#   - null → Problema T-1503-AGENT (no procesó)
```

---

## 🎯 Recomendaciones para Epic US-015

### Prioridad P0 (Bloqueadores)

1. **T-1502-INFRA: Storage Naming Convention**
   - Formalizar nomenclatura: `models/low-poly/{uuid}_{timestamp}.glb`
   - Garantizar URLs siempre absolutas con `https://`
   - Configurar CORS en bucket Supabase

2. **T-1504-BACK: API Contract Enforcement**
   - Pydantic schema estricto con `HttpUrl` (no `str`)
   - Validar que `low_poly_url` nunca sea NULL en respuestas (usar filtro DB)
   - OpenAPI docs actualizadas

3. **T-1505-FRONT: Zod Validation**
   - Crear `PartDetailSchema` con Zod
   - Validar TODAS las respuestas de API antes de usar
   - Rechazar URLs relativas en runtime

### Prioridad P1 (High Impact)

4. **T-1503-AGENT: Idempotency + Retry**
   - Implementar lógica: Si task falla, retry 3 veces con backoff
   - DB: Añadir campo `processing_status: "pending" | "processing" | "completed" | "failed"`
   - Frontend: Mostrar spinner si `processing_status === "processing"`

5. **T-1506-FRONT: Null URL Handling**
   - Componente `<ModelLoader />`: Detectar `low_poly_url === null`
   - Mostrar placeholder: "⏳ Procesando geometría... (30-60s)"
   - Polling: Refetch cada 5s hasta que `low_poly_url !== null`

### Prioridad P2 (Nice to Have)

6. **T-1507-TEST: E2E Cypress Test**
   - Test completo: Upload .3dm → Wait for processing → Verify canvas render
   - Assertions: GLB URL absoluta, bbox presente, modelo visible en canvas

---

## 📚 Anexos

### Anexo A: PoC File Structure

```
poc/formats-comparison/
├── index.html                           # Vite entry point
├── package.json                         # React + Three.js + Vite deps
├── TROUBLESHOOTING.md                   # Known issues (Brep → Mesh)
├── ARCHITECTURE_DECISION.md             # ADR-001: InstanceObjects strategy
├── src/
│   ├── App.tsx                          # ✅ Main app (hardcoded GLB path)
│   ├── main.tsx                         # Vite mount point
│   ├── viewers/
│   │   ├── GltfDracoViewer.tsx          # ✅ Three.js canvas + useGLTF
│   │   └── ComparisonView.tsx           # (unused — format comparison UI)
│   └── hooks/
│       └── useBenchmark.ts              # Performance metrics
├── exporters/
│   ├── export_instances_gltf.py         # ✅ CORE: Rhino → glTF+Draco
│   ├── test_instance_objects.py         # Diagnostic tool
│   ├── requirements.txt                 # rhino3dm, trimesh, pygltflib
│   └── PREPROCESSING_REQUIRED.md        # Manual Brep → Mesh guide
└── dataset/
    ├── raw/                             # Input .3dm files (user uploads here)
    └── gltf-draco/                      # Output .glb files (served by Vite)
```

### Anexo B: Actual File Structure (Relevant)

```
src/
├── backend/
│   ├── main.py                          # FastAPI app entry
│   ├── api/
│   │   ├── upload.py                    # POST /api/upload
│   │   └── parts.py                     # GET /api/parts, GET /api/parts/{id}
│   ├── schemas.py                       # Pydantic models (⚠️ Informal)
│   └── config.py                        # Supabase settings
├── agent/
│   ├── tasks/
│   │   ├── geometry_processing.py       # ✅ generate_low_poly_glb task
│   │   └── file_validation.py           # US-002 validation
│   └── constants.py                     # TASK_GENERATE_LOW_POLY_GLB
└── frontend/
    ├── src/
    │   ├── components/
    │   │   ├── ModelLoader.tsx          # ✅ useGLTF wrapper
    │   │   ├── Dashboard/               # Canvas con N piezas
    │   │   │   ├── PartMesh.tsx
    │   │   │   └── BBoxProxy.tsx
    │   │   └── PartDetailModal.tsx      # T-1007-FRONT (modal detail)
    │   ├── services/
    │   │   └── upload.service.ts        # ⚠️ API calls (sin Zod)
    │   └── types/
    │       └── parts.ts                 # TypeScript interfaces (⚠️ Sin validación runtime)
    └── package.json                     # React + R3F + Drei
```

### Anexo C: URLs Reales vs Esperadas

**PoC:**
```
http://localhost:5173/gltf-draco/model.glb
                      └─────┬──────┘
                     Static path relativo a Vite
```

**Actual (Correcto):**
```
https://xyz.supabase.co/storage/v1/object/public/models/low-poly/abc123.glb
└────────┬────────┘ └──────────────┬──────────────┘ └────┬────┘ └───┬────┘
  Absoluto           Supabase Storage endpoint       Bucket  Path+File
```

**Actual (Incorrecto - detectado en logs):**
```
models/low-poly/abc123.glb    ❌ Relativa (falta https://)
./models/low-poly/abc123.glb  ❌ Relativa (falta origen)
/storage/v1/...abc123.glb     ❌ Path sin dominio
```

---

## 🔖 Referencias

- [POC Troubleshooting](../poc/formats-comparison/TROUBLESHOOTING.md)
- [ADR-001: InstanceObjects Strategy](../poc/formats-comparison/ARCHITECTURE_DECISION.md)
- [US-002: Validation Spec](../US-002/README.md)
- [US-005: Dashboard 3D](../US-005/README.md)
- [US-010: 3D Viewer](../US-010/README.md) (modal detail component)
- [Epic US-015: Refactorización E2E](./README.md)

---

**Documento versionado:** v1.0  
**Próximo paso:** Generar JSON-CONTRACTS.md con schema canónico  
**Feedback:** Compartir con equipo antes de empezar T-1501-DB
