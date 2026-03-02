# Sagrada Família Parts Manager (SF-PM)

> **Digital Twin Activo para Gestión de Inventario de Piezas CAD con Validación Inteligente**

[![Status](https://img.shields.io/badge/Status-In%20Development-yellow)](./docs/00-index.md)
[![Documentation](https://img.shields.io/badge/Docs-100%25-green)](./docs/)
[![License](https://img.shields.io/badge/License-MIT-blue)](./LICENSE)

---

## 🎯 Descripción

Sistema enterprise que transforma archivos CAD estáticos (Rhino .3dm) en un **gemelo digital activo** para la gestión integral del inventario de decenas de miles de piezas únicas de la Sagrada Família de Barcelona.

**Características clave:**
- ✅ Búsquedas instantáneas (de 3 horas a 10 minutos)
- ✅ Validación automática con IA ("The Librarian" Agent)
- ✅ Trazabilidad completa del ciclo de vida
- ✅ Visualización 3D en navegador (Three.js)
- ✅ Eliminación de errores logísticos (40% → 0%)

---

## 📚 Documentación

**Documentación completa disponible en [`/docs`](./docs/)**

### Índice de Documentación Técnica

| Fase | Documento | Descripción |
|------|-----------|-------------|
| **Índice** | [📑 00-index.md](./docs/00-index.md) | Índice general del proyecto y guía de navegación |
| **Fase 1** | [📘 01-strategy.md](./docs/01-strategy.md) | Análisis del problema y propuesta de valor |
| **Fase 2** | [📘 02-prd.md](./docs/02-prd.md) | Product Requirements Document (PRD) completo |
| **Fase 3** | [📘 03-service-model.md](./docs/03-service-model.md) | Lean Canvas y modelo de negocio |
| **Fase 4** | [📘 04-use-cases.md](./docs/04-use-cases.md) | Casos de uso maestros y diagramas de flujo |
| **Fase 5** | [📘 05-data-model.md](./docs/05-data-model.md) | Modelo de datos PostgreSQL/Supabase |
| **Fase 6** | [📘 06-architecture.md](./docs/06-architecture.md) | Arquitectura Cloud-Native (C4 Model) |
| **Fase 7** | [📘 07-agent-design.md](./docs/07-agent-design.md) | Diseño del agente IA "The Librarian" |
| **Fase 8** | [📘 08-roadmap.md](./docs/08-roadmap.md) | Roadmap de implementación |

---

## 🛠️ Stack Tecnológico

```yaml
Frontend:  React 18 + TypeScript + Three.js / React-Three-Fiber + Zustand + Vite
Backend:   FastAPI (Python 3.11) + Celery Workers + Redis
Agent:     rhino3dm 8 + trimesh + open3d (validación y conversión 3D low-poly)
Database:  PostgreSQL 15 (Docker) + Supabase Cloud (Auth + Realtime)
Storage:   Supabase Storage (S3-compatible) + CloudFront CDN
CAD:       rhino3dm + glTF/GLB + pipeline de decimación low-poly
Infra:     Docker Compose (5 servicios) + GitHub Actions CI/CD
```

---

## 🚀 Quick Start

### Prerrequisitos

- Docker (Engine) & Docker Compose
- GNU Make (o `make` compatible). En Windows puede usarse `test.bat` o WSL.
- Variables de entorno configuradas en `.env` (ver `.env.example`)

### Quick Start (Docker + Make)

1. Clonar repositorio y preparar `.env`:

```bash
git clone https://github.com/sagrada-familia/parts-manager.git
cd parts-manager
cp .env.example .env
# Edita .env con los valores reales (SUPABASE_URL, SUPABASE_KEY, DATABASE_PASSWORD, REDIS_PASSWORD, etc.)
```

2. Levantar servicios en contenedores (dev):

```bash
make up-db        # Solo la base de datos
make up-backend   # Backend + dependencias (db + redis)
make up-frontend  # Frontend dev server (Vite)
```

3. Inicializar infra (crear buckets / semillas necesarias):

```bash
make init-db
```

4. O levantar todos los servicios a la vez (backend + frontend + agent-worker):

```bash
make up
# Frontend:   http://localhost:5173
# Backend API: http://localhost:8000
# API Docs:    http://localhost:8000/docs
```

> **Nota**: Python, Node.js, Redis y PostgreSQL **no son necesarios en el host**. Todo el entorno corre dentro de Docker.

### Testing

Ejecutar la suite de tests:

**Backend:**
```bash
make test        # Ejecuta todos los tests backend (unit + integration)
make test-infra  # Ejecuta tests de infraestructura / integración
make test-storage # Ejecuta test específico de storage
```

**Frontend:**
```bash
make front-install  # Instala dependencias npm dentro de Docker
make test-front     # Ejecuta tests de frontend (Vitest)
make up-frontend    # Inicia servidor de desarrollo Vite
make front-shell    # Abre shell en contenedor frontend
```

### Desarrollo Frontend

Para trabajar con el frontend (React + TypeScript + Vite):

1. Instalar dependencias (primera vez):
```bash
make front-install
```

2. Iniciar servidor de desarrollo:
```bash
make up-frontend
# Accede a http://localhost:5173
```

3. Ejecutar tests en modo watch:
```bash
make test-front
```

### Notas rápidas

- **Node.js NO requerido en el host**: Todo el desarrollo frontend se ejecuta dentro de Docker.
- Volumen anónimo `/app/node_modules` evita conflictos entre Windows y contenedor.
- Para crear o resetear la infraestructura de storage use `make init-db`.
- Las pruebas de integración requieren que las variables `SUPABASE_URL` y `SUPABASE_KEY` estén disponibles en el entorno donde se ejecutan.

**Más información**: Ver [Documentación técnica](./docs)

---

## 🤖 Desarrollo Asistido por IA

Este proyecto utiliza **Claude Code** (claude-sonnet-4-6) como asistente de desarrollo.

### Guías de Trabajo
- **[AGENTS.MD](./AGENTS.md)**: Reglas globales del AI Assistant (logging, workflow, definition of done)
- **[AI Best Practices](./.github/AI-BEST-PRACTICES.md)**: Guía de mejores prácticas para trabajo eficiente con el AI
- **[prompts.md](./prompts.md)**: Registro completo de todos los prompts utilizados (trazabilidad)

### CI/CD Pipeline
- **[CI/CD Guide](./.github/CI-CD-GUIDE.md)**: Documentación completa del pipeline GitHub Actions
- **[Secrets Setup](./.github/SECRETS-SETUP.md)**: ⚠️ **ACCIÓN REQUERIDA** - Configurar secrets antes de merge

**Estado del CI/CD**: ✅ **Activo** — 5 jobs: lint, test-backend, test-frontend, security-scan (Trivy + pip-audit + npm audit), build Docker
Ver configuración en [SECRETS-SETUP.md](./.github/SECRETS-SETUP.md)

### Memory Bank
Sistema de estado compartido para trabajo multi-agente:
- **[memory-bank/activeContext.md](./memory-bank/activeContext.md)**: Contexto actual y tareas activas
- **[memory-bank/systemPatterns.md](./memory-bank/systemPatterns.md)**: Patrones arquitectónicos
- **[memory-bank/techContext.md](./memory-bank/techContext.md)**: Stack tecnológico completo
- **[memory-bank/decisions.md](./memory-bank/decisions.md)**: ADRs (Architecture Decision Records)

---

## 📊 Estado del Proyecto

✅ **Completado (Entrega 2)**:
- **US-001**: Upload de archivos .3dm con presigned URLs y validación
- **US-002**: Validación automática con agente "The Librarian" (Celery + rhino3dm)
- **US-005**: Dashboard 3D interactivo de piezas (Three.js + LOD + filtros + Zustand)
- **US-010**: Visor 3D Web (PartDetailModal, ModelLoader, ErrorBoundary, CDN)
- **Tests**: ~400+ PASS (backend + frontend + agent, cobertura >80%)
- **DevSecOps**: multi-stage Docker, healthchecks, resource limits, CI/CD (GitHub Actions)

🔮 **Pendiente (Entrega 3)**:
- US-007: Cambio de estado con ciclo de vida completo
- US-013: Login y autenticación (Supabase Auth)
- US-009: Evidencia de fabricación (foto en completado)

---

## 📄 Licencia

Proyecto académico (TFM) con código open-source bajo [MIT License](./LICENSE).  
Datos reales de la Sagrada Família no incluidos por confidencialidad.

---

## 📞 Contacto

- **Documentación**: [`/docs`](./docs/)
- **Email**: [Ver repositorio oficial]
- **GitHub**: [@pedrocortesark](https://github.com/pedrocortesark)

---

<p align="center">
  <i>Construido con ❤️ para la gestión del patrimonio arquitectónico mundial</i>
</p>
