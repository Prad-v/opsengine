# Keep / OpsEngine local development helpers
#
# One command for day-to-day coding:
#   make start       # install if needed + Docker deps (incl. provider-mock) + backend + frontend
#
# Other modes:
#   make up          # full stack in Docker with live-mounted source
#   make local       # production Dockerfiles built from this checkout
#   make prod        # pull published images from the registry
#   make help        # list targets

SHELL := /bin/bash
.DEFAULT_GOAL := help

export DOCKER_BUILDKIT ?= 1
export COMPOSE_DOCKER_CLI_BUILD ?= 1

COMPOSE ?= docker compose
STATE_DIR := state
PYTHON ?= python3.11
VENV_DIR ?= .venv
VENV_PYTHON := $(VENV_DIR)/bin/python
VENV_PIP := $(VENV_DIR)/bin/pip
VENV_POETRY := $(VENV_DIR)/bin/poetry
KEEP_BIN := $(VENV_DIR)/bin/keep
UI_DIR := keep-ui
UI_ENV := $(UI_DIR)/.env.local

COMPOSE_TEMPORAL := -f docker-compose.temporal.yml
COMPOSE_DEV := -f docker-compose.dev.yml $(COMPOSE_TEMPORAL)
COMPOSE_LOCAL := -f docker-compose.local.yml $(COMPOSE_TEMPORAL)
COMPOSE_PROD := -f docker-compose.yml
COMPOSE_DEPS := -f docker-compose.deps.yml $(COMPOSE_TEMPORAL)
COMPOSE_MOCK := -f backend/services/provider-mock/docker-compose.yml
COMPOSE_WHEELS := -f docker-compose.alpine-wheels.yml

# Host-process backend defaults (overridable: `make backend AUTH_TYPE=NO_AUTH`)
export AUTH_TYPE ?= DB
export KEEP_JWT_SECRET ?= keep-dev-jwt-secret-change-me
export KEEP_DEFAULT_USERNAME ?= admin
export KEEP_DEFAULT_PASSWORD ?= admin
# Admin API key for local scripts / provider-mock (AUTH_TYPE=DB). Format: name:role:secret
# Use mock-admin to match existing local DBs that already provisioned this reference id.
export KEEP_DEFAULT_API_KEYS ?= mock-admin:admin:keepappkey
export SECRET_MANAGER_TYPE ?= FILE
export SECRET_MANAGER_DIRECTORY ?= ./$(STATE_DIR)
export DATABASE_CONNECTION_STRING ?= postgresql+psycopg2://keepuser:keeppassword@localhost:5432/keepdb
export PUSHER_APP_ID ?= 1
export PUSHER_APP_KEY ?= keepappkey
export PUSHER_APP_SECRET ?= keepappsecret
export PUSHER_HOST ?= localhost
export PUSHER_PORT ?= 6001
export LOG_FORMAT ?= dev_terminal
export POSTHOG_DISABLED ?= true
export SENTRY_DISABLED ?= true
export PORT ?= 8080
export PYTHONPATH ?= $(CURDIR)
# Optional Redis worker path (deps compose exposes Redis on 6379)
export REDIS ?= false
export REDIS_HOST ?= localhost
export REDIS_PORT ?= 6379
export REDIS_DB ?= 0

.PHONY: help ensure-state ensure-venv \
	up up-d build rebuild logs ps restart down \
	dev local local-d local-build local-down \
	prod prod-d prod-down \
	deps deps-up deps-down deps-logs deps-ps deps-wait \
	install install-backend install-frontend env-frontend ensure-install \
	backend frontend start run hybrid stop hybrid-stop \
	mock-providers mock-providers-down mock-providers-test \
	temporal-worker temporal-worker-down register-list-and-zip-catalog \
	register-nvidia-gpu-catalog register-nvidia-gpu-alert-codes \
	register-payments-alert-codes \
	demo-list-and-zip demo-nvidia-gpu register-nvidia-gpu-topology \
	synthetic-checks synthetic-checks-down register-probe-targets-catalog \
	register-ai-dc-synthetic-checks \
	kind-up kind-down k8s-start k8s-start-fresh k8s-prod k8s-ui k8s-stop k8s-e2e k8s-load \
	api-alpine-wheels \
	clean clean-images

help: ## Show available targets
	@echo "Keep local development"
	@echo ""
	@echo "Single command (recommended):"
	@echo "  make start             Install if needed + Docker deps + backend + frontend"
	@echo "                         UI http://localhost:3000  API http://localhost:8080"
	@echo "                         Temporal UI http://localhost:8233"
	@echo "                         Provider mock http://localhost:8099 (Grafana/Mimir/VM + NVIDIA GPU)"
	@echo "                         NetBox http://localhost:8000 (admin/admin; seed from mock Topology tab)"
	@echo "                         Auto-setup: NVIDIA GPU remediate workflow + Temporal catalog"
	@echo "                         Workers: keep-ops + keep-synth (synthetic checks)"
	@echo "                         Default auth: DB (admin/admin) — change password on first login"
	@echo "  make stop              Stop host API/UI and Docker deps (incl. provider-mock)"
	@echo ""
	@echo "Split terminals (optional):"
	@echo "  make deps / make backend / make frontend"
	@echo "                         deps = Postgres, Redis, Soketi, Temporal,"
	@echo "                         temporal-worker (keep-ops), synthetic-checks (keep-synth),"
	@echo "                         provider-mock (http://localhost:8099) + NetBox (http://localhost:8000)"
	@echo ""
	@echo "Full Docker:"
	@echo "  make up                Dev images + mounted source"
	@echo "  make local             Production Dockerfiles from this checkout"
	@echo "  make api-alpine-wheels Precompile Alpine grpcio wheels (once per grpcio version)"
	@echo "  make prod              Pull published keep-api / keep-ui images"
	@echo ""
	@echo "Provider mock (also started by make start / make deps):"
	@echo "  make mock-providers      Restart mock UI + NetBox (http://localhost:8099 / :8000)"
	@echo "  make mock-providers-test Run provider-mock tests in Docker"
	@echo "  make temporal-worker     Build/start Temporal keep-ops worker"
	@echo "  make register-list-and-zip-catalog  Register ListAndZipDirectory in catalog"
	@echo "  make register-nvidia-gpu-catalog    Register RemediateNvidiaGpu in catalog"
	@echo "  make register-nvidia-gpu-alert-codes Register NVIDIA_GPU_* reserved codes"
	@echo "  make register-payments-alert-codes  Register HIGH_CPU / HIGH_MEMORY / DISK_SPACE_LOW"
	@echo "  make register-nvidia-gpu-topology    Seed NVIDIA region/row/rack/GPU topology"
	@echo "  make demo-list-and-zip    Install mock→Temporal ListAndZip e2e demo"
	@echo "  make demo-nvidia-gpu     Re-run NVIDIA GPU remediate e2e setup (also done by make start)"
	@echo "  make synthetic-checks    Build/start Temporal keep-synth worker"
	@echo "  make register-probe-targets-catalog  Register ProbeTargets in catalog"
	@echo "  make register-ai-dc-synthetic-checks Seed NVIDIA/AMD inference+training synthetics"
	@echo ""
	@echo "Kubernetes (kind + Helm, two namespaces):"
	@echo "  make k8s-start         Local-dev ns 'keep': backend/worker/mock + host UI"
	@echo "                         API http://localhost:8080  UI http://localhost:3000"
	@echo "  make k8s-start-fresh   Same as k8s-start but --no-cache (recompile grpcio + backend)"
	@echo "  make k8s-prod          Prod ns 'keep-prod': official/CI-artifact Helm images + in-cluster UI"
	@echo "  make k8s-stop          Delete the opsengine kind cluster"
	@echo "  make k8s-e2e           NVIDIA GPU remediations e2e against the kind deploy"
	@echo "  make k8s-load          Burst-ingest events (COUNT=2000; COUNT=1000000 for a day)"
	@echo "  make kind-up / kind-down   Aliases for k8s-start / k8s-stop"
	@echo ""
	@awk 'BEGIN {FS = ":.*## "}; /^[a-zA-Z0-9_-]+:.*?## / {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

ensure-state: ## Create writable state directory for secrets / sqlite
	@mkdir -p $(STATE_DIR)
	@chmod 0777 $(STATE_DIR) 2>/dev/null || true

# ---------------------------------------------------------------------------
# Hybrid: host Python/Node + Docker dependencies
# ---------------------------------------------------------------------------

ensure-venv: ## Create .venv with python3.11 and install Poetry into it
	@command -v $(PYTHON) >/dev/null || { \
		echo "ERROR: $(PYTHON) not found."; \
		echo "Install Python 3.11 (e.g. brew install python@3.11) and retry."; \
		exit 1; \
	}
	@$(PYTHON) -c 'import xml.parsers.expat' >/dev/null 2>&1 || { \
		echo "ERROR: $(PYTHON) cannot import xml.parsers.expat (broken Homebrew Python)."; \
		echo "Try: brew reinstall python@3.11 expat"; \
		exit 1; \
	}
	@if [ ! -x "$(VENV_PYTHON)" ] || ! "$(VENV_PYTHON)" -c 'import sys' >/dev/null 2>&1; then \
		echo "Creating virtualenv at $(VENV_DIR) with $$($(PYTHON) -V)..."; \
		rm -rf "$(VENV_DIR)"; \
		$(PYTHON) -m venv "$(VENV_DIR)"; \
	fi
	@test -x "$(VENV_PYTHON)" || { echo "ERROR: failed to create $(VENV_PYTHON)"; exit 1; }
	@echo "Using virtualenv: $$($(VENV_PYTHON) -V) ($(VENV_PYTHON))"
	@$(VENV_PIP) install -q -U pip setuptools wheel
	@if [ ! -x "$(VENV_POETRY)" ]; then \
		echo "Installing Poetry into $(VENV_DIR)..."; \
		$(VENV_PIP) install -q "poetry>=1.8,<3"; \
	fi

install: install-backend install-frontend ## Install backend (poetry) and frontend (npm) deps

install-backend: ensure-venv ## Create .venv and install Keep backend deps
	@echo "Installing backend dependencies into $(VENV_DIR)..."
	VIRTUAL_ENV="$(CURDIR)/$(VENV_DIR)" \
	POETRY_VIRTUALENVS_CREATE=false \
	POETRY_VIRTUALENVS_IN_PROJECT=true \
	$(VENV_POETRY) install --no-interaction
	@test -x "$(KEEP_BIN)" || { echo "ERROR: $(KEEP_BIN) missing after poetry install"; exit 1; }
	@echo "Backend ready."
	@echo "  Activate: source $(VENV_DIR)/bin/activate"
	@echo "  Or run:   make backend"

install-frontend: env-frontend ## Install keep-ui npm dependencies
	@command -v npm >/dev/null || { echo "npm not found. Install Node.js 20+"; exit 1; }
	cd $(UI_DIR) && npm install
	@echo "Frontend ready. Run via: make frontend"

env-frontend: ## Ensure keep-ui/.env.local exists
	@if [ ! -f "$(UI_ENV)" ]; then \
		cp $(UI_DIR)/.env.local.example $(UI_ENV); \
		printf '\nAUTH_TYPE=DB\nNEXTAUTH_SECRET=%s\n' "$$(openssl rand -hex 32)" >> $(UI_ENV); \
		echo "Created $(UI_ENV)"; \
	else \
		echo "$(UI_ENV) already exists"; \
	fi

deps: deps-up ## Alias for deps-up

deps-up: ## Start postgres, redis, soketi, Temporal, workers, and provider-mock in Docker
	$(COMPOSE) $(COMPOSE_DEPS) up -d --build
	$(COMPOSE) $(COMPOSE_MOCK) up --build -d
	@$(MAKE) deps-wait
	@echo ""
	@echo "Dependencies ready:"
	@echo "  Postgres          localhost:5432  (keepuser/keeppassword, db=keepdb)"
	@echo "  Redis             localhost:6379"
	@echo "  Soketi            localhost:6001"
	@echo "  Temporal          localhost:7233  (UI http://localhost:8233, namespace=default)"
	@echo "  temporal-worker   keep-ops queue (ListAndZipDirectory, RemediateNvidiaGpu)"
	@echo "  synthetic-checks  keep-synth queue (ProbeTarget / ProbeTargetGroup / ProbeTargets)"
	@echo "  Provider mock     http://localhost:8099  (Grafana/Mimir/VM + NVIDIA GPU alerts)"
	@echo "  NetBox            http://localhost:8000  (admin/admin; seed from mock Topology tab)"

deps-wait: ## Wait until dependency healthchecks pass
	@echo "Waiting for dependency healthchecks..."
	@for i in $$(seq 1 90); do \
		if $(COMPOSE) $(COMPOSE_DEPS) exec -T keep-database pg_isready -U keepuser -d keepdb >/dev/null 2>&1 \
			&& $(COMPOSE) $(COMPOSE_DEPS) exec -T keep-redis redis-cli ping >/dev/null 2>&1 \
			&& $(COMPOSE) $(COMPOSE_DEPS) exec -T temporal temporal operator cluster health --address 127.0.0.1:7233 >/dev/null 2>&1 \
			&& curl -sf http://127.0.0.1:8099/api/health >/dev/null 2>&1; then \
			echo "Dependencies are healthy."; \
			exit 0; \
		fi; \
		sleep 1; \
	done; \
	echo "Timed out waiting for dependencies. Check: make deps-logs / make mock-providers"; \
	exit 1

deps-down: ## Stop Docker dependencies (incl. provider-mock)
	-$(COMPOSE) $(COMPOSE_MOCK) down
	$(COMPOSE) $(COMPOSE_DEPS) down

deps-logs: ## Follow dependency container logs
	$(COMPOSE) $(COMPOSE_DEPS) logs -f

deps-ps: ## Show dependency container status
	$(COMPOSE) $(COMPOSE_DEPS) ps
	@$(COMPOSE) $(COMPOSE_MOCK) ps
ensure-install: ## Install backend/frontend only if missing
	@need_backend=0; need_frontend=0; \
	if [ ! -x "$(KEEP_BIN)" ]; then need_backend=1; fi; \
	if [ ! -d "$(UI_DIR)/node_modules" ]; then need_frontend=1; fi; \
	if [ "$$need_backend" = "1" ] || [ "$$need_frontend" = "1" ]; then \
		echo "Installing missing local dependencies..."; \
		if [ "$$need_backend" = "1" ]; then $(MAKE) install-backend; fi; \
		if [ "$$need_frontend" = "1" ]; then $(MAKE) install-frontend; fi; \
	else \
		echo "Local dependencies already installed (.venv + node_modules)."; \
	fi

backend: ensure-state ## Run Keep API from project .venv
	@test -x "$(KEEP_BIN)" || { echo "Backend venv missing. Run: make install-backend"; exit 1; }
	@echo "Using $(KEEP_BIN)"
	@echo "DATABASE_CONNECTION_STRING=$(DATABASE_CONNECTION_STRING)"
	$(KEEP_BIN) api --host 0.0.0.0 --port $(PORT)

frontend: env-frontend ## Run Keep UI on the host (npm)
	@test -d $(UI_DIR)/node_modules || { echo "Run 'make install-frontend' first"; exit 1; }
	cd $(UI_DIR) && npm run dev

start: ensure-state ensure-install deps-up ## One command: install + deps + backend/frontend + GPU demo setup
	@chmod +x scripts/run-hybrid-local.sh
	./scripts/run-hybrid-local.sh

run: start ## Alias for start
hybrid: start ## Alias for start

stop: ## Stop host API/UI and Docker dependencies (incl. provider-mock)
	@pkill -f "$(KEEP_BIN) api" 2>/dev/null || true
	@pkill -f "poetry run keep api" 2>/dev/null || true
	@pkill -f "keep api" 2>/dev/null || true
	@pkill -f "next dev" 2>/dev/null || true
	-$(COMPOSE) $(COMPOSE_MOCK) down
	-$(COMPOSE) $(COMPOSE_DEPS) down
	@echo "Stopped backend, frontend, Docker deps, and provider-mock."

hybrid-stop: stop ## Alias for stop

mock-providers: ## Restart provider-mock UI only (also started by make start / make deps)
	$(COMPOSE) $(COMPOSE_MOCK) up --build -d
	@echo ""
	@echo "Provider mock UI: http://localhost:8099"
	@echo "NetBox:           http://localhost:8000  (admin/admin; first boot 1–2 min)"
	@echo "Register a mock provider, then Send event to validate Keep ingestion."

mock-providers-down: ## Stop provider mock service
	$(COMPOSE) $(COMPOSE_MOCK) down

mock-providers-test: ## Run provider-mock tests inside Docker
	$(COMPOSE) $(COMPOSE_MOCK) --profile test run --rm --build provider-mock-test

temporal-worker: ## Build and start the Temporal keep-ops worker
	$(COMPOSE) $(COMPOSE_TEMPORAL) up -d --build temporal-worker
	@echo ""
	@echo "Temporal worker polling queue keep-ops (ListAndZipDirectory)."
	@echo "Register catalog: make register-list-and-zip-catalog"

temporal-worker-down: ## Stop Temporal worker (leaves Temporal server running)
	$(COMPOSE) $(COMPOSE_TEMPORAL) stop temporal-worker

register-list-and-zip-catalog: ## Register ListAndZipDirectory in Keep Temporal catalog
	@chmod +x scripts/register_temporal_list_and_zip_catalog.py
	$(VENV_PYTHON) scripts/register_temporal_list_and_zip_catalog.py

register-nvidia-gpu-catalog: ## Register RemediateNvidiaGpu in Keep Temporal catalog
	@chmod +x scripts/register_temporal_nvidia_gpu_catalog.py
	$(VENV_PYTHON) scripts/register_temporal_nvidia_gpu_catalog.py

register-nvidia-gpu-alert-codes: ## Register reserved NVIDIA_GPU_* codes in the alert catalog
	@chmod +x scripts/register_alert_codes_nvidia_gpu.py
	$(VENV_PYTHON) scripts/register_alert_codes_nvidia_gpu.py

register-payments-alert-codes: ## Register reserved HIGH_CPU / HIGH_MEMORY / DISK_SPACE_LOW codes
	@chmod +x scripts/register_alert_codes_payments.py
	$(VENV_PYTHON) scripts/register_alert_codes_payments.py

register-nvidia-gpu-topology: ## Seed NVIDIA region/datacenter/row/rack/GPU Service Topology
	@chmod +x scripts/register_nvidia_gpu_topology.py
	$(VENV_PYTHON) scripts/register_nvidia_gpu_topology.py

demo-list-and-zip: ## Install mock Grafana → Temporal ListAndZip e2e demo workflow
	@chmod +x scripts/demo_mock_list_and_zip.sh
	./scripts/demo_mock_list_and_zip.sh

demo-nvidia-gpu: ## Re-run NVIDIA GPU remediate e2e setup (also auto-run by make start)
	@chmod +x scripts/demo_mock_nvidia_gpu.sh
	./scripts/demo_mock_nvidia_gpu.sh

synthetic-checks: ## Build and start the Temporal keep-synth synthetic-checks worker
	$(COMPOSE) $(COMPOSE_TEMPORAL) up -d --build synthetic-checks
	@echo ""
	@echo "Synthetic-checks worker polling queue keep-synth (ProbeTargetGroup / ProbeTargets)."
	@echo "UI: Catalog → Synthetic checks   Mode 2: make register-probe-targets-catalog"

synthetic-checks-down: ## Stop synthetic-checks worker (leaves Temporal server running)
	$(COMPOSE) $(COMPOSE_TEMPORAL) stop synthetic-checks

register-probe-targets-catalog: ## Register ProbeTargets in Keep Temporal catalog
	@chmod +x scripts/register_temporal_probe_targets_catalog.py
	$(VENV_PYTHON) scripts/register_temporal_probe_targets_catalog.py

register-ai-dc-synthetic-checks: ## Seed NVIDIA/AMD inference+training synthetic checks
	@chmod +x scripts/register_ai_dc_synthetic_checks.py
	$(VENV_PYTHON) scripts/register_ai_dc_synthetic_checks.py

# ---------------------------------------------------------------------------
# Dev: build from Dockerfile.dev.* and mount local code (hot reload)
# ---------------------------------------------------------------------------

up: ensure-state ## Build from local source, mount code, run in foreground
	$(COMPOSE) $(COMPOSE_DEV) up --build

up-d: ensure-state ## Same as up, detached
	$(COMPOSE) $(COMPOSE_DEV) up --build -d

dev: up ## Alias for up

build: ensure-state ## Rebuild dev images from local Dockerfiles
	$(COMPOSE) $(COMPOSE_DEV) build

rebuild: ensure-state ## Force rebuild of dev images (no cache)
	$(COMPOSE) $(COMPOSE_DEV) build --no-cache

logs: ## Follow dev stack logs
	$(COMPOSE) $(COMPOSE_DEV) logs -f

ps: ## Show running containers (dev)
	$(COMPOSE) $(COMPOSE_DEV) ps

restart: ## Restart dev stack
	$(COMPOSE) $(COMPOSE_DEV) restart

down: ## Stop and remove the dev stack
	$(COMPOSE) $(COMPOSE_DEV) down

# ---------------------------------------------------------------------------
# Local: production Dockerfiles built from this checkout (no registry pull)
# ---------------------------------------------------------------------------

local: ensure-state api-alpine-wheels ## Build prod Dockerfiles from source and run (foreground)
	$(COMPOSE) $(COMPOSE_LOCAL) up --build

local-d: ensure-state api-alpine-wheels ## Build prod Dockerfiles from source and run (detached)
	$(COMPOSE) $(COMPOSE_LOCAL) up --build -d

api-alpine-wheels: ## Precompile Alpine musl wheels (grpcio) into keep-api-alpine-wheels:py313 (once per version; ~20–40 min first time)
	$(COMPOSE) $(COMPOSE_WHEELS) build alpine-wheels

local-build: ensure-state api-alpine-wheels ## Build local production images only
	$(COMPOSE) $(COMPOSE_LOCAL) build

local-down: ## Stop the local-build stack
	$(COMPOSE) $(COMPOSE_LOCAL) down

# ---------------------------------------------------------------------------
# Prod: published images from Artifact Registry
# ---------------------------------------------------------------------------

prod: ensure-state ## Pull published images and run docker-compose.yml
	$(COMPOSE) $(COMPOSE_PROD) up

prod-d: ensure-state ## Pull published images and run detached
	$(COMPOSE) $(COMPOSE_PROD) up -d

prod-down: ## Stop the published-image stack
	$(COMPOSE) $(COMPOSE_PROD) down

# ---------------------------------------------------------------------------
# Kubernetes (kind + Helm)
# ---------------------------------------------------------------------------

k8s-start: ## Local-dev namespace (keep): local backend/worker/mock, then host UI
	@chmod +x scripts/deploy_kind.sh scripts/k8s_ui.sh
	MODE=dev K8S_UI=1 ./scripts/deploy_kind.sh

k8s-start-fresh: ## Same as k8s-start but --no-cache (recompile grpcio + backend/worker/mock)
	@chmod +x scripts/deploy_kind.sh scripts/k8s_ui.sh
	MODE=dev K8S_UI=1 K8S_FRESH=1 ./scripts/deploy_kind.sh

k8s-prod: ## Prod namespace (keep-prod): published Helm / CI artifact images + in-cluster UI
	@chmod +x scripts/deploy_kind.sh
	MODE=prod ./scripts/deploy_kind.sh

k8s-ui: ## Restart host UI only (already started by make k8s-start)
	@chmod +x scripts/k8s_ui.sh
	./scripts/k8s_ui.sh

k8s-stop: ## Delete the opsengine kind cluster
	-kind delete cluster --name opsengine

k8s-e2e: ## Run NVIDIA GPU remediations e2e against the kind deploy
	@chmod +x scripts/e2e_k8s_nvidia_gpu.sh
	./scripts/e2e_k8s_nvidia_gpu.sh

COUNT ?= 2000
CONCURRENCY ?= 20
BATCH_SIZE ?= 20

k8s-load: ## Burst-ingest events against kind API (COUNT=2000; COUNT=1000000 for a full day)
	python3 scripts/load_k8s_events.py --count $(COUNT) --concurrency $(CONCURRENCY) --batch-size $(BATCH_SIZE)

kind-up: k8s-start ## Alias for k8s-start

kind-down: k8s-stop ## Alias for k8s-stop

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

clean: ## Stop all compose modes and remove orphan containers
	-$(COMPOSE) $(COMPOSE_DEV) down --remove-orphans
	-$(COMPOSE) $(COMPOSE_LOCAL) down --remove-orphans
	-$(COMPOSE) $(COMPOSE_PROD) down --remove-orphans
	-$(COMPOSE) $(COMPOSE_DEPS) down --remove-orphans
	-$(COMPOSE) $(COMPOSE_TEMPORAL) down --remove-orphans
	-$(COMPOSE) $(COMPOSE_MOCK) --profile test down --remove-orphans
	-$(COMPOSE) $(COMPOSE_MOCK) down --remove-orphans

clean-images: clean ## Also remove locally built Keep images
	-docker rmi keep-frontend-dev:local keep-backend-dev:local keep-frontend:local keep-backend:local 2>/dev/null || true
