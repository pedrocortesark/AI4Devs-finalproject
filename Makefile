.PHONY: build build-prod up-backend up-frontend up down init-db setup-events migrate test test-all test-infra test-unit test-integration test-storage shell clean front-install test-front front-shell help

# Force bash as shell (required on Windows with GnuWin32 make)
SHELL := bash
.SHELLFLAGS := -euo pipefail -c

# ===== DOCKER LIFECYCLE =====

# Build Docker images (dev targets)
build:
	docker compose build

# Build production images
build-prod:
	docker build --target prod -t sf-pm-backend:prod --file src/backend/Dockerfile src/backend
	docker build --target prod -t sf-pm-frontend:prod --file src/frontend/Dockerfile src/frontend
	docker build --target prod -t sf-pm-agent:prod --file src/agent/Dockerfile src/agent

# Test production images locally (use docker-compose.prod.yml)
up-prod:
	docker compose -f docker-compose.prod.yml up -d

# Stop production test containers
down-prod:
	docker compose -f docker-compose.prod.yml down

# Clean production test data
clean-prod:
	docker compose -f docker-compose.prod.yml down -v

# Run security scan with Trivy
scan-security:
	@echo "🔒 Scanning backend image..."
	docker build --target prod -t sf-pm-backend:scan --file src/backend/Dockerfile src/backend
	docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest image --severity HIGH,CRITICAL sf-pm-backend:scan
	@echo ""
	@echo "🔒 Scanning agent image..."
	docker build --target prod -t sf-pm-agent:scan --file src/agent/Dockerfile src/agent
	docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest image --severity HIGH,CRITICAL sf-pm-agent:scan
	@echo ""
	@echo "🔒 Scanning frontend image..."
	docker build --target prod -t sf-pm-frontend:scan --file src/frontend/Dockerfile src/frontend
	docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest image --severity HIGH,CRITICAL sf-pm-frontend:scan

# Lint Dockerfiles with Hadolint
lint-docker:
	@echo "🔍 Linting Dockerfiles..."
	docker run --rm -i hadolint/hadolint < src/backend/Dockerfile
	docker run --rm -i hadolint/hadolint < src/agent/Dockerfile
	docker run --rm -i hadolint/hadolint < src/frontend/Dockerfile

# Start backend + its dependencies (redis only)
up-backend:
	docker compose up -d backend

# Start all services
up:
	docker compose up -d

# Stop all services (without removing volumes)
down:
	docker compose down

# Clean up containers and volumes
clean:
	docker compose down -v
	docker system prune -f

# ===== BACKEND COMMANDS =====

# Initialize database infrastructure (create buckets, policies)
init-db:
	docker compose run --rm --no-deps backend python /app/infra/init_db.py

# Setup events table for T-004-BACK (automated via psycopg2)
setup-events:
	docker compose run --rm backend python /app/infra/setup_events_table.py

# Apply all migrations to Supabase
# Uses Docker to run psql — no local psql installation needed.
# Requires SUPABASE_DATABASE_URL in .env
# Usage: make migrate
migrate:
	@echo "☁️  Applying all migrations to Supabase..."
	@set -a && source .env && set +a && \
	if [ -z "$$SUPABASE_DATABASE_URL" ]; then \
		echo "❌ SUPABASE_DATABASE_URL is not set. Check your .env file."; \
		exit 1; \
	fi && \
	for file in supabase/migrations/*.sql; do \
		echo "  Applying $$file..."; \
		MSYS_NO_PATHCONV=1 docker run --rm \
			--dns 8.8.8.8 --dns 8.8.4.4 \
			-v "$$(pwd)/supabase/migrations:/migrations" \
			postgres:15-alpine \
			psql "$$SUPABASE_DATABASE_URL" -f "/migrations/$$(basename $$file)" || exit 1; \
	done && \
	echo "✅ All migrations applied successfully"

# Run all tests inside Docker (backend + agent)
test:
	@echo "🧪 Running backend tests (includes unit + integration)..."
	docker compose run --rm backend pytest -v --ignore=tests/integration/test_validate_file_task.py --ignore=tests/integration/test_user_strings_e2e.py --ignore=tests/integration/test_celery_worker.py || true
	@echo "🤖 Running agent tests (celery/worker-specific)..."
	docker compose run --rm agent-worker python -m pytest tests/unit/ tests/integration/test_user_strings_e2e.py tests/integration/test_validate_file_task.py tests/integration/test_celery_worker.py --ignore=tests/unit/test_validation_service.py --ignore=tests/unit/test_validation_report_service.py --ignore=tests/unit/test_upload_service_enqueue.py --ignore=tests/unit/test_validate_file_red.py --ignore=tests/unit/test_validation_schema_presence.py --ignore=tests/unit/test_parts_service.py --ignore=tests/unit/test_rhino_parser_service.py --ignore=tests/unit/test_navigation_service.py --ignore=tests/unit/test_part_detail_service.py --ignore=tests/unit/test_elements_service.py --ignore=tests/unit/test_storage_utils.py -v

# Run only agent tests (unit + agent-specific integration)
# Note: Excludes backend-specific unit tests that require src/backend/services/ imports
# (validation_service, validation_report_service, upload_service_enqueue, parts_service, navigation_service, part_detail_service, elements_service, storage_utils)
# These tests run in 'make test-unit' using backend container where imports work correctly
test-agent:
	docker compose run --rm agent-worker python -m pytest tests/unit/ tests/integration/test_user_strings_e2e.py tests/integration/test_validate_file_task.py tests/integration/test_celery_worker.py --ignore=tests/unit/test_validation_service.py --ignore=tests/unit/test_validation_report_service.py --ignore=tests/unit/test_upload_service_enqueue.py --ignore=tests/unit/test_validate_file_red.py --ignore=tests/unit/test_validation_schema_presence.py --ignore=tests/unit/test_parts_service.py --ignore=tests/unit/test_rhino_parser_service.py --ignore=tests/unit/test_navigation_service.py --ignore=tests/unit/test_part_detail_service.py --ignore=tests/unit/test_elements_service.py --ignore=tests/unit/test_storage_utils.py -v

# Run only integration tests (backend)
test-infra:
	docker compose run --rm backend pytest tests/integration/ --ignore=tests/integration/test_validate_file_task.py --ignore=tests/integration/test_user_strings_e2e.py --ignore=tests/integration/test_celery_worker.py -v

# Run only unit tests (backend)
test-unit:
	docker compose run --rm --no-deps backend pytest tests/unit/ -v

# Run backend tests quickly (unit + core integration, no slow tests)
test-backend-quick:
	@echo "🧪 Running backend tests (fast)..."
	docker compose run --rm backend pytest tests/unit/ tests/integration/test_blocks_schema_t0503.py tests/integration/test_block_status_enum_extension.py tests/integration/test_storage_config.py tests/integration/parts_api/ -m "not slow" -v

# Run specific integration test
test-storage:
	docker compose run --rm --no-deps backend pytest tests/integration/test_storage_config.py -v

# Open a shell inside the backend container
shell:
	docker compose run --rm backend /bin/sh

# ===== FRONTEND COMMANDS =====

# Start frontend dev server
up-frontend:
	docker compose up frontend

# Install frontend dependencies inside Docker
front-install:
	docker compose run --rm -u root frontend npm install

# Run frontend tests (TDD workflow)
test-front:
	docker compose run --rm -u root frontend bash -c "npm install && npm test"

# Open a shell inside the frontend container
front-shell:
	docker compose run --rm frontend /bin/sh

# ===== TEST PROFILES (isolated test containers) =====

# Run all tests via profile containers (backend + frontend)
test-all:
	docker compose --profile test run --rm test-backend
	docker compose --profile test run --rm test-frontend

# ===== HELP =====

help:
	@echo "Available commands:"
	@echo ""
	@echo "  Docker lifecycle:"
	@echo "    make build         - Build Docker images (dev)"
	@echo "    make build-prod    - Build production images (all services)"
	@echo "    make up-backend    - Start backend + its dependencies (redis only)"
	@echo "    make up            - Start all services (dev mode)"
	@echo "    make up-prod       - Start all services (prod images, local test)"
	@echo "    make down          - Stop all services"
	@echo "    make down-prod     - Stop production test containers"
	@echo "    make clean         - Stop + remove volumes + prune (dev)"
	@echo "    make clean-prod    - Stop + remove volumes (prod test)"
	@echo ""
	@echo "  Security & Quality:"
	@echo "    make scan-security - Run Trivy vulnerability scan on all images"
	@echo "    make lint-docker   - Lint all Dockerfiles with Hadolint"
	@echo ""
	@echo "  Backend:"
	@echo "    make init-db       - Initialize DB infrastructure (buckets, policies)"
	@echo "    make setup-events  - Create events table in Supabase (T-004-BACK)"
	@echo "    make migrate-t0503   - Apply T-0503-DB migration (low_poly_url + bbox)"
	@echo "    make migrate-all     - Apply all migrations (local Docker db, legacy)"
	@echo "    make migrate-local   - Apply all migrations to local Docker DB (requires: make up-db)"
	@echo "    make migrate-cloud   - Apply all migrations to Supabase cloud (prod)"
	@echo "    make test          - Run all tests (backend + agent)"
	@echo "    make test-agent    - Run agent tests only"
	@echo "    make test-unit     - Run backend unit tests only"
	@echo "    make test-infra    - Run backend integration tests only"
	@echo "    make test-storage  - Run storage infrastructure test"
	@echo "    make shell         - Open shell in backend container"
	@echo ""
	@echo "  Frontend:"
	@echo "    make up-frontend   - Start frontend dev server (Vite)"
	@echo "    make front-install - Install frontend dependencies (npm install)"
	@echo "    make test-front    - Run frontend tests (Vitest)"
	@echo "    make front-shell   - Open shell in frontend container"
	@echo ""
	@echo "  Test profiles:"
	@echo "    make test-all      - Run all tests via isolated profile containers"
