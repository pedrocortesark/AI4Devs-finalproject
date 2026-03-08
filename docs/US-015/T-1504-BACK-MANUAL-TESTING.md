# T-1504-BACK - Manual Testing Guide

**Fecha:** 2026-03-08  
**Ticket:** T-1504-BACK (API Integration with Element Contract)  
**Status:** ✅ DONE - Ready for manual validation  

---

## 📋 Overview

Este documento te guía para probar manualmente la API de Elements sin depender del frontend (que está pendiente en T-1505-FRONT).

### ✅ Backend Changes Implemented

1. **Schemas Renamed:**
   - `PartCanvasItem` → `Element`
   - `PartDetail` → `ElementDetail`
   - `PartsListResponse` → `ElementsListResponse`

2. **New Endpoints:**
   - `GET /api/elements` (lista con filtros)
   - `GET /api/elements/{id}` (detalle)
   - `GET /api/elements/{id}/navigation` (prev/next)

3. **Material Type Field:**
   - Campo `material_type` es TEXT (no enum)
   - Validación contra 63 materiales reales: Montjuïc, Ulldecona, Floresta, etc.
   - Backend valida en application layer con `constants.VALID_MATERIALS`

4. **Render-Ready Filtering:**
   - Solo devuelve elementos con `low_poly_url IS NOT NULL` y `bbox IS NOT NULL`
   - Filtros opcionales: `material_type`, `status`, `limit`, `offset`

---

## 🚀 Quick Start

### Option 1: Automated Script (Recommended)

```bash
# Test Local Dev
./scripts/test-elements-api.sh dev

# Test Production (Railway)
./scripts/test-elements-api.sh prod
```

El script ejecuta 8 tests automáticos:
1. Health Check
2. List Elements (render-ready)
3. Element Detail
4. Navigation (Prev/Next)
5. Filter by Material Type
6. Filter by Status
7. Error Handling (Invalid Material)
8. Error Handling (404)

### Option 2: Manual cURL Commands

Ver sección **Manual Test Commands** más abajo.

---

## 🧪 Test Scenarios

### 1️⃣ Health Check

**Objetivo:** Verificar que el backend está disponible.

```bash
# Dev
curl http://localhost:8000/ready | jq

# Prod
curl https://sf-pm.up.railway.app/ready | jq
```

**Expected Response:**
```json
{
  "status": "ok",
  "database": "connected"
}
```

---

### 2️⃣ List Elements (Render-Ready Only)

**Objetivo:** Verificar que solo devuelve elementos con geometría procesada.

```bash
# Dev
curl 'http://localhost:8000/api/elements?limit=10' | jq

# Prod
curl 'https://sf-pm.up.railway.app/api/elements?limit=10' | jq
```

**Expected Response:**
```json
{
  "elements": [
    {
      "id": "uuid-here",
      "iso_code": "GLPER.B-PAE0720",
      "material_type": "Montjuïc",
      "status": "validated",
      "created_at": "2026-03-07T19:00:00Z",
      "low_poly_url": "https://...",
      "bbox": {
        "min": [-1.5, -2.0, 0.0],
        "max": [1.5, 2.0, 3.5]
      }
    }
  ],
  "meta": {
    "total": 25,
    "filtered": 6
  }
}
```

**✅ Validation Checks:**
- Todos los elementos tienen `low_poly_url` (no null)
- Todos los elementos tienen `bbox` con estructura `{min: [x,y,z], max: [x,y,z]}`
- `material_type` es un string (ej: "Montjuïc", "Ulldecona")
- `meta.filtered` ≤ `meta.total` (algunos elementos no tienen geometría)

---

### 3️⃣ Element Detail

**Objetivo:** Obtener detalles completos de un elemento.

```bash
# Replace {element_id} with real UUID from Step 2
ELEMENT_ID="..."  # Copy from previous step

# Dev
curl "http://localhost:8000/api/elements/$ELEMENT_ID" | jq

# Prod
curl "https://sf-pm.up.railway.app/api/elements/$ELEMENT_ID" | jq
```

**Expected Response:**
```json
{
  "id": "uuid-here",
  "iso_code": "GLPER.B-PAE0720",
  "material_type": "Montjuïc",
  "status": "validated",
  "created_at": "2026-03-07T19:00:00Z",
  "low_poly_url": "https://...",
  "bbox": {
    "min": [-1.5, -2.0, 0.0],
    "max": [1.5, 2.0, 3.5]
  },
  "validation_report": {
    "status": "passed",
    "errors": []
  }
}
```

**✅ Validation Checks:**
- Todos los campos presentes (no nulls en campos requeridos)
- `validation_report` tiene estructura `{status: string, errors: array}`

---

### 4️⃣ Navigation (Prev/Next)

**Objetivo:** Obtener IDs de elementos adyacentes para navegación canvas.

```bash
# Dev
curl "http://localhost:8000/api/elements/$ELEMENT_ID/navigation" | jq

# Prod
curl "https://sf-pm.up.railway.app/api/elements/$ELEMENT_ID/navigation" | jq
```

**Expected Response:**
```json
{
  "prev_id": "uuid-of-previous",
  "next_id": "uuid-of-next",
  "current_index": 3,
  "total_count": 6
}
```

**✅ Validation Checks:**
- Si es el primer elemento: `prev_id = null`
- Si es el último elemento: `next_id = null`
- `current_index` es 1-based (rango: 1 a `total_count`)
- `total_count` coincide con `meta.filtered` del endpoint list

---

### 5️⃣ Filter by Material Type

**Objetivo:** Validar que el filtro `material_type` funciona correctamente.

```bash
# Dev - Filter by Montjuïc
curl 'http://localhost:8000/api/elements?material_type=Montjuïc&limit=5' | jq

# Prod
curl 'https://sf-pm.up.railway.app/api/elements?material_type=Montjuïc&limit=5' | jq
```

**Expected Behavior:**
- Todos los elementos devueltos tienen `material_type = "Montjuïc"`
- Si no hay elementos con ese material, devuelve array vacío (no error)

**Test Invalid Material:**
```bash
curl 'http://localhost:8000/api/elements?material_type=InvalidStone' | jq
```

**Expected Response (422 Validation Error):**
```json
{
  "detail": "Invalid material type 'InvalidStone'. Must be one of: Montjuïc, Ulldecona, Floresta, ..."
}
```

---

### 6️⃣ Filter by Status

**Objetivo:** Validar que el filtro `status` funciona correctamente.

```bash
# Dev
curl 'http://localhost:8000/api/elements?status=validated&limit=5' | jq

# Prod
curl 'https://sf-pm.up.railway.app/api/elements?status=validated&limit=5' | jq
```

**Expected Behavior:**
- Todos los elementos devueltos tienen `status = "validated"`
- Status válidos: `uploaded`, `processing`, `processed`, `validated`, `failed`, `archived`

---

### 7️⃣ Error Handling - Non-Existent Element

**Objetivo:** Verificar respuesta 404 para elementos inexistentes.

```bash
# Dev
curl -i 'http://localhost:8000/api/elements/00000000-0000-0000-0000-000000000000'

# Prod
curl -i 'https://sf-pm.up.railway.app/api/elements/00000000-0000-0000-0000-000000000000'
```

**Expected Response:**
```
HTTP/1.1 404 Not Found

{
  "detail": "Element not found"
}
```

---

## 📊 Expected Test Results

| Test Scenario | Dev | Prod | Notes |
|---------------|-----|------|-------|
| 1. Health Check | ✅ | ✅ | Should return `{"status": "ok"}` |
| 2. List Elements | ✅ | ✅ | Should return 6+ render-ready elements |
| 3. Element Detail | ✅ | ✅ | Should return full element with bbox |
| 4. Navigation | ✅ | ✅ | Should return prev/next IDs or null |
| 5. Filter Material | ✅ | ✅ | Should filter by Montjuïc correctly |
| 6. Filter Status | ✅ | ✅ | Should filter by validated correctly |
| 7. Invalid Material | ✅ | ✅ | Should return 422 validation error |
| 8. Non-Existent (404) | ✅ | ✅ | Should return 404 error |

---

## 🔍 Troubleshooting

### ❌ No Elements Returned (`meta.filtered = 0`)

**Causa:** Base de datos vacía o elementos sin geometría procesada.

**Solución:**
```bash
# Option 1: Upload test fixtures
make upload-fixtures

# Option 2: Reprocess existing elements
echo "yes" | docker compose run --rm backend python infra/reprocess_parts_with_bbox.py
```

### ❌ Connection Refused (Dev)

**Causa:** Backend no está corriendo.

**Solución:**
```bash
make up-backend
# Wait ~10 seconds for startup
curl http://localhost:8000/ready
```

### ❌ 500 Internal Server Error

**Causa:** Error en backend (migration no aplicada, Redis down, etc.)

**Solución:**
```bash
# Check logs
docker compose logs backend --tail=50

# Verify database migration
docker compose exec backend alembic current

# Restart services
make down && make up
```

### ❌ Railway Returns 502/503 (Prod)

**Causa:** Deployment falló o servicio en cold start.

**Solución:**
```bash
# Check deployment logs in Railway dashboard
# Trigger redeploy if needed
# Wait 30-60 seconds for cold start
```

---

## 📝 Manual Test Commands (Copy-Paste)

### Dev Environment

```bash
# Set base URL
BASE_URL="http://localhost:8000"

# 1. Health Check
curl "$BASE_URL/ready" | jq

# 2. List Elements
curl "$BASE_URL/api/elements?limit=10" | jq

# 3. Get Element ID (store in variable)
ELEMENT_ID=$(curl -s "$BASE_URL/api/elements?limit=1" | jq -r '.elements[0].id')
echo "Element ID: $ELEMENT_ID"

# 4. Element Detail
curl "$BASE_URL/api/elements/$ELEMENT_ID" | jq

# 5. Navigation
curl "$BASE_URL/api/elements/$ELEMENT_ID/navigation" | jq

# 6. Filter by Material
curl "$BASE_URL/api/elements?material_type=Montjuïc&limit=5" | jq

# 7. Filter by Status
curl "$BASE_URL/api/elements?status=validated&limit=5" | jq

# 8. Error - Invalid Material
curl "$BASE_URL/api/elements?material_type=InvalidStone" | jq

# 9. Error - Non-Existent Element
curl "$BASE_URL/api/elements/00000000-0000-0000-0000-000000000000" | jq
```

### Prod Environment

```bash
# Set base URL
BASE_URL="https://sf-pm.up.railway.app"

# Copy all commands from Dev section above
# (replace http://localhost:8000 with BASE_URL variable)
```

---

## ✅ Acceptance Criteria Validation

| Acceptance Criteria | Test Command | Expected Result |
|---------------------|--------------|-----------------|
| **AC1:** Endpoint renamed to `/api/elements` | `curl $BASE_URL/api/elements` | Returns `ElementsListResponse` schema |
| **AC2:** `material_type` is string (not enum) | Inspect response JSON | Field is `"Montjuïc"` (string), not `{"type": "Stone"}` |
| **AC3:** Only render-ready elements returned | Check `low_poly_url` and `bbox` | All elements have both fields (not null) |
| **AC4:** Validation rejects invalid materials | `curl ...?material_type=InvalidStone` | Returns 422 HTTP error |
| **AC5:** `workshop_id` field removed | Inspect response JSON | Field does not exist in response |

---

## 🎯 Next Steps

1. **Run Automated Script:**
   ```bash
   ./scripts/test-elements-api.sh dev
   ./scripts/test-elements-api.sh prod
   ```

2. **Verify Results:**
   - All 8 tests should pass (✅)
   - Note any failures or unexpected behavior

3. **Report Issues:**
   - If tests fail, share output and Docker logs:
     ```bash
     docker compose logs backend --tail=100 > backend-logs.txt
     ```

4. **Frontend Integration (Next):**
   - Once backend validated → Start T-1505-FRONT
   - Update frontend to use `/api/elements` endpoint
   - Integrate `material_type` string validation

---

## 📎 References

- **Audit Report:** `docs/US-015/AUDIT-T-1504-BACK-FINAL.md`
- **Tech Spec:** `docs/US-015/T-1504-BACK-TechnicalSpec.md`
- **Prompts Log:** `prompts.md` (entries #216-#219)
- **Backend Code:**
  - Schemas: `src/backend/schemas.py` (Element, ElementDetail, ElementsListResponse)
  - Service: `src/backend/services/elements_service.py`
  - API: `src/backend/api/elements.py`
  - Constants: `src/backend/constants.py` (VALID_MATERIALS with 63 entries)

---

**Status:** ✅ Ready for manual testing  
**Last Updated:** 2026-03-08 por AI Assistant
