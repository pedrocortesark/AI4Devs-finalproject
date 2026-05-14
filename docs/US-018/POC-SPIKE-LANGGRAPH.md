# PoC Spike LangGraph — Especificación Técnica

**Fecha:** 3 de Mayo de 2026  
**Sprint:** Sprint 11 — Semana 1, Día 1  
**Duración:** 1 día (8 horas)  
**Responsable:** Dev Team  
**Estado:** 🔴 PENDIENTE (bloqueado por aprobación Sagrada Família)

---

## 🎯 Objetivo

Validar técnicamente la **viabilidad de integrar LangGraph** con la arquitectura existente de SF-PM (Celery + Redis + Supabase) ANTES de invertir 5 semanas (38 horas) en US-018 completo.

**Pregunta crítica a responder:**  
> ¿Puede LangGraph StateGraph ejecutarse dentro de un Celery task, persistir estado en Redis, y escribir resultados en Supabase sin romper los 415 tests baseline?

---

## 📋 Contexto Estratégico

### Por Qué es Mandatorio

Según [PRE-IMPLEMENTATION-ANALYSIS.md](PRE-IMPLEMENTATION-ANALYSIS.md) § 3.1:

> **Riesgo técnico (Probabilidad: MEDIA, Impacto: ALTO):**  
> LangGraph es relativamente nuevo (v0.0.20). Si encontramos incompatibilidades con Celery/Redis/Supabase en **semana 3** después de invertir 2 semanas de desarrollo, perdemos **€1,600** en rework y retrasamos entrega 2 sprints.

**Mitigación:**  
PoC Spike día 1 reduce riesgo de 50% → 10% con inversión de solo 8 horas.

### Decision Gate Post-Spike

```
PoC Spike (Day 1) → Decision:
                     ├─ ✅ SUCCESS → Proceder con T-1801 a T-1810 (30.5 SP)
                     └─ ❌ FAIL → Pivotear a alternativa:
                                  - Opción A: Temporal.io
                                  - Opción B: Celery Canvas puro
                                  - Opción C: Reducir scope (clasificación regex only)
```

**Criterio de decisión:**  
- Si ≥4/6 criterios de éxito cumplen → GO
- Si <4/6 criterios cumplen → Escalar a Tech Lead + reevaluar arquitectura

---

## ✅ Criterios de Éxito (6 Obligatorios)

### 1. **Instalación Compatible** ✅
- `langgraph>=0.0.20` instala sin conflictos de dependencias
- Compatible con Python 3.11 + FastAPI 0.109 + Celery 5.3
- `poetry lock` o `pip install` sin errores
- Docker rebuild exitoso

**Validación:**
```bash
docker compose run --rm backend python -c "import langgraph; print(langgraph.__version__)"
# Debe imprimir: 0.0.20 o superior
```

### 2. **StateGraph Básico Ejecuta** ✅
- Crear StateGraph con 3-4 nodos (subset de los 8 finales)
- Transiciones condicionales funcionan
- Estado se pasa correctamente entre nodos
- NO crashes, NO memory leaks evidentes

**Implementación mínima:**
```python
from langgraph.graph import StateGraph, END
from typing import TypedDict

class ValidationState(TypedDict):
    block_id: str
    nomenclature_valid: bool
    geometry_valid: bool
    tipologia: str | None
    confidence: float | None

def validate_nomenclature(state: ValidationState) -> ValidationState:
    # Mock: siempre válido para PoC
    return {**state, "nomenclature_valid": True}

def extract_geometry(state: ValidationState) -> ValidationState:
    # Mock: siempre válido
    return {**state, "geometry_valid": True}

def classify_mock(state: ValidationState) -> ValidationState:
    # Mock LLM (NO consumir OpenAI en spike)
    return {**state, "tipologia": "dovela", "confidence": 0.85}

# StateGraph setup
graph = StateGraph(ValidationState)
graph.add_node("validate_nomenclature", validate_nomenclature)
graph.add_node("extract_geometry", extract_geometry)
graph.add_node("classify", classify_mock)

graph.set_entry_point("validate_nomenclature")
graph.add_edge("validate_nomenclature", "extract_geometry")
graph.add_edge("extract_geometry", "classify")
graph.add_edge("classify", END)

compiled_graph = graph.compile()

# Test invocation
result = compiled_graph.invoke({
    "block_id": "test-001",
    "nomenclature_valid": False,
    "geometry_valid": False,
    "tipologia": None,
    "confidence": None
})

assert result["nomenclature_valid"] == True
assert result["tipologia"] == "dovela"
```

### 3. **Integración Celery Funciona** ✅
- StateGraph ejecuta dentro de Celery task
- Redis no crashea con estado de LangGraph
- Task completa exitosamente (status SUCCESS en Celery)
- Timeout razonable (<30s para mock)

**Implementación:**
```python
# src/agent/tasks.py
from infra.celery_client import celery_app
from .poc_graph import compiled_graph

@celery_app.task(name="poc_langgraph_validate")
def poc_validate_block(block_id: str):
    """PoC: Ejecutar LangGraph dentro de Celery task."""
    result = compiled_graph.invoke({
        "block_id": block_id,
        "nomenclature_valid": False,
        "geometry_valid": False,
        "tipologia": None,
        "confidence": None
    })
    return result

# Enqueue from backend
from src.agent.tasks import poc_validate_block
task = poc_validate_block.delay("GLPER.B-PAE0720.0701")
task.get(timeout=30)  # Debe completar sin timeout
```

### 4. **Persistencia Supabase** ✅
- Escribir resultado en tabla `blocks` campo `semantic_data`
- JSON serializa correctamente (tipologia, confidence)
- UPDATE sin errores de concurrencia
- Datos legibles desde frontend

**Validación SQL:**
```python
# Después de task
from infra.supabase_client import get_supabase_client

supabase = get_supabase_client()
block = supabase.table("blocks").select("semantic_data").eq("id", "test-001").execute()

assert block.data[0]["semantic_data"]["tipologia"] == "dovela"
assert block.data[0]["semantic_data"]["confidence"] == 0.85
assert block.data[0]["semantic_data"]["classification_method"] == "mock"
```

### 5. **Zero Regresión Tests Baseline** ✅
- **415 tests baseline** (US-001 a US-015) siguen pasando
- NO romper imports existentes
- NO side effects en Celery workers existentes
- CI/CD pipeline verde

**Comando validación:**
```bash
docker compose run --rm backend pytest tests/unit/ tests/integration/ -v --tb=short
# Debe pasar: 415/415 tests (100%)
```

### 6. **Transiciones Condicionales** ✅
- Implementar al menos 1 edge condicional
- Ejemplo: si `nomenclature_valid == False` → saltar a END (fail-fast)
- Validar que NO ejecuta nodos posteriores si falla

**Implementación:**
```python
def should_continue_after_nomenclature(state: ValidationState) -> str:
    if state["nomenclature_valid"]:
        return "extract_geometry"
    else:
        return END

graph.add_conditional_edges(
    "validate_nomenclature",
    should_continue_after_nomenclature,
    {
        "extract_geometry": "extract_geometry",
        END: END
    }
)

# Test fail-fast
result_fail = compiled_graph.invoke({
    "block_id": "test-invalid",
    "nomenclature_valid": False,  # Forzar fallo
    # ...
})
# Verificar que NO ejecutó extract_geometry ni classify
assert "geometry_valid" not in result_fail or result_fail["geometry_valid"] == False
```

---

## 🚫 Fuera de Scope (NO implementar)

Para mantener el spike en 8 horas, **NO** implementar:

- ❌ LLM real (OpenAI GPT-4) — usar mock
- ❌ Circuit Breaker pattern — diferir a T-1802
- ❌ 8 nodos completos — con 3-4 basta
- ❌ Frontend integration — solo backend
- ❌ Tests unitarios nuevos — solo validar baseline
- ❌ rhino3dm geometry extraction — mock geometría
- ❌ Logging/observability detallado — console.log básico
- ❌ Rate limiting — diferir a T-1810
- ❌ Prompt engineering — diferir a T-1802

---

## 📦 Entregables (EOD Day 1)

### 1. Código PoC (Mínimo Viable)

Estructura de archivos:
```
src/
└── agent/
    ├── __init__.py
    ├── poc_graph.py           ← StateGraph básico (NEW)
    ├── poc_nodes.py           ← 3-4 nodos mock (NEW)
    └── tasks.py               ← Celery task wrapper (MODIFIED)
```

### 2. Documento de Resultados

**`docs/US-018/POC-SPIKE-RESULTS.md`** con:
- ✅/❌ por cada criterio (6 total)
- Screenshots de Celery logs
- Evidencia tests baseline (415/415 PASS)
- Decisión: GO/NO-GO con justificación
- Riesgos identificados (si los hay)
- Tiempo invertido real vs estimado (8h)

### 3. Decision Record (si NO-GO)

Si spike falla, crear **`memory-bank/decisions.md`** entrada:
```markdown
## ADR-003: Alternativa a LangGraph (2026-05-03)

**Contexto:** PoC Spike LangGraph falló en criterio X/Y/Z.

**Decisión:** Pivotear a [Temporal.io / Celery Canvas / Regex-only].

**Consecuencias:**
- Timeline ajustado: 5 semanas → X semanas
- Story Points ajustados: 30.5 SP → Y SP
- Trade-offs: ...
```

---

## ⏱️ Timeline Detallado (8 horas)

### Hora 1-2: Setup (2h)
- Instalar `langgraph` en `pyproject.toml`
- Rebuild Docker container
- Verificar imports básicos
- Leer documentación LangGraph oficial

### Hora 3-4: StateGraph Básico (2h)
- Crear `poc_graph.py` con 3 nodos
- Implementar transiciones condicionales
- Test invocation local (fuera de Celery)
- Debug imports/typing

### Hora 5-6: Integración Celery (2h)
- Crear Celery task wrapper
- Enqueue desde backend API (endpoint temporal `/poc/test`)
- Verificar Redis no crashea
- Logs Celery worker

### Hora 7: Persistencia Supabase (1h)
- Escribir resultado en `blocks.semantic_data`
- Validar JSON serializa correctamente
- Query desde psql para verificar

### Hora 8: Validación + Reporte (1h)
- Ejecutar tests baseline (415 tests)
- Crear POC-SPIKE-RESULTS.md
- Decision: GO/NO-GO
- Commit código PoC (branch `poc/langgraph-spike`)

---

## 🎓 Criterios de Calidad

### Mínimo Aceptable (4/6 criterios)
- Si cumple ≥4 criterios → **GO** (continuar con US-018)
- Riesgos residuales documentados + mitigación en T-1801

### Ideal (6/6 criterios)
- Todos los criterios pasan → **GO con confianza alta**
- Proceder directamente a T-1801 sin ajustes

### Crítico (≤3 criterios)
- **NO-GO** → Escalar a Tech Lead
- Reevaluar arquitectura (ADR-003)
- Considerar alternativas (Temporal.io, Celery Canvas, scope reducido)

---

## 🔗 Referencias

- **Gap Analysis:** [PRE-IMPLEMENTATION-ANALYSIS.md](PRE-IMPLEMENTATION-ANALYSIS.md)
- **Backlog US-018:** [docs/09-mvp-backlog.md](../09-mvp-backlog.md) línea 755-898
- **LangGraph Docs:** https://langchain-ai.github.io/langgraph/
- **Arquitectura AI:** [docs/meetings/sagrada-familia/12-ai-architecture.md](../meetings/sagrada-familia/12-ai-architecture.md)

---

## 📝 Notas de Implementación

### Dependencias Nuevas

```toml
# pyproject.toml
[tool.poetry.dependencies]
langgraph = "^0.0.20"
langchain-core = "^0.1.0"
```

### Variables de Entorno (NO necesarias en PoC)

```bash
# .env (NO configurar OpenAI aún)
# OPENAI_API_KEY=sk-... ← NO necesario, usar mock
ENABLE_LANGGRAPH_POC=true  # Feature flag
```

### Endpoint Temporal para Testing

```python
# src/backend/api/poc.py (temporal, eliminar después)
from fastapi import APIRouter
from src.agent.tasks import poc_validate_block

router = APIRouter(prefix="/poc", tags=["PoC"])

@router.post("/test-langgraph/{block_id}")
def test_langgraph_spike(block_id: str):
    """Endpoint temporal para PoC Spike. ELIMINAR después."""
    task = poc_validate_block.delay(block_id)
    return {"task_id": task.id, "status": "queued"}
```

---

## ⚠️ Riesgos Identificados Pre-Spike

| Riesgo | Probabilidad | Mitigación |
|--------|--------------|------------|
| LangGraph incompatible con Celery serialization | MEDIA | Probar serialización estado en Hora 5 |
| Redis memory overhead con StateGraph | BAJA | Monitorear Redis memory usage |
| Typing conflicts con TypedDict | MEDIA | Usar `from __future__ import annotations` |
| Performance degradation (>30s timeout) | BAJA | Medir tiempos en cada nodo |

---

## ✅ Checklist Pre-Spike

Antes de comenzar el spike, verificar:

- [ ] Docker containers running (`make up`)
- [ ] Redis accesible (ping test)
- [ ] Supabase connection OK (health check)
- [ ] 415 tests baseline passing (pre-requisito)
- [ ] Branch `poc/langgraph-spike` creado
- [ ] 8 horas bloqueadas en calendario (sin interrupciones)

---

**Estado Actual:** 🔴 PENDIENTE  
**Blocker:** Aprobación Sagrada Família (May 3-5)  
**ETA Inicio:** May 9, 2026 (Sprint 11 Day 1)
