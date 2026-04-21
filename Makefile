SHELL := /usr/bin/env bash

COMPOSE_FILE        := docker-compose.yml
RESOLVED_FILE       := docker-compose.resolved.yml
GPU_OVERRIDE_FILE   := docker-compose.gpu.yml
ENV_FILE            := .env
ENV_EXAMPLE         := .env.example
PORT_RESOLVER       := ./find_free_ports_docker-compose.sh
COMPOSE             := docker compose -f $(RESOLVED_FILE) -f $(GPU_OVERRIDE_FILE) --env-file $(ENV_FILE)

.DEFAULT_GOAL := help

.PHONY: help up down start stop restart build rebuild logs ps status urls env resolve-ports gpu-override clean nuke

help:
	@echo ""
	@echo "=================================================================="
	@echo "  vLLM Manager - Makefile"
	@echo "=================================================================="
	@echo ""
	@echo "  To bring the whole system up, run:"
	@echo ""
	@echo "      make up"
	@echo ""
	@echo "  Available targets:"
	@echo "    make up             Bring the whole system up (env + GPU detect + ports + build + start)"
	@echo "    make down           Stop and remove containers"
	@echo "    make start          Start existing containers"
	@echo "    make stop           Stop containers without removing them"
	@echo "    make restart        Restart all services"
	@echo "    make build          (Re)build images"
	@echo "    make rebuild        Build from scratch (no cache) and start"
	@echo "    make logs           Tail service logs (CTRL+C to quit)"
	@echo "    make ps             Show service status"
	@echo "    make urls           Print frontend/backend URLs and ports"
	@echo "    make env            Create .env from .env.example if missing"
	@echo "    make gpu-override   Regenerate docker-compose.gpu.yml from detected /dev/nvidiaN"
	@echo "    make resolve-ports  Regenerate docker-compose.resolved.yml"
	@echo "    make clean          Remove containers AND volumes (DATA LOSS)"
	@echo "    make nuke           clean + remove built images"
	@echo ""

up:
	@echo ""
	@echo "=================================================================="
	@echo "  Bringing up vLLM Manager"
	@echo "=================================================================="
	@echo ""
	@echo "[1/5] Preparing environment file (.env)..."
	@$(MAKE) --no-print-directory env
	@echo ""
	@echo "[2/5] Detecting NVIDIA GPUs on host..."
	@$(MAKE) --no-print-directory gpu-override
	@echo ""
	@echo "[3/5] Resolving host port conflicts..."
	@$(MAKE) --no-print-directory resolve-ports
	@echo ""
	@echo "[4/5] Building images and starting containers..."
	@$(COMPOSE) up -d --build
	@echo ""
	@echo "[5/5] Current service status:"
	@$(COMPOSE) ps
	@echo ""
	@echo "=================================================================="
	@echo "  System is up."
	@echo ""
	@FRONTEND_PORT=$$($(COMPOSE) port frontend 80 2>/dev/null | awk -F: '{print $$NF}'); \
	BACKEND_PORT=$$($(COMPOSE) port backend 8080 2>/dev/null | awk -F: '{print $$NF}'); \
	echo "  Frontend URL: http://127.0.0.1:$${FRONTEND_PORT:-unknown}"; \
	echo "  Backend API:  http://127.0.0.1:$${BACKEND_PORT:-unknown}"
	@echo ""
	@echo "  Useful commands:"
	@echo "    make logs     - follow logs"
	@echo "    make ps       - show status"
	@echo "    make urls     - show service URLs"
	@echo "    make down     - stop everything"
	@echo "=================================================================="
	@echo ""

down:
	@if [ -f $(RESOLVED_FILE) ] && [ -f $(GPU_OVERRIDE_FILE) ]; then \
		echo "Stopping and removing containers..."; \
		$(COMPOSE) down; \
	else \
		echo "Compose files not found - nothing to stop."; \
	fi

start:
	$(COMPOSE) start

stop:
	$(COMPOSE) stop

restart:
	$(COMPOSE) restart

build: env gpu-override resolve-ports
	$(COMPOSE) build

rebuild: env gpu-override resolve-ports
	$(COMPOSE) build --no-cache
	$(COMPOSE) up -d

logs:
	$(COMPOSE) logs -f --tail=200

ps status:
	$(COMPOSE) ps

urls:
	@FRONTEND_PORT=$$($(COMPOSE) port frontend 80 2>/dev/null | awk -F: '{print $$NF}'); \
	BACKEND_PORT=$$($(COMPOSE) port backend 8080 2>/dev/null | awk -F: '{print $$NF}'); \
	echo "Frontend URL: http://127.0.0.1:$${FRONTEND_PORT:-not running}"; \
	echo "Backend API:  http://127.0.0.1:$${BACKEND_PORT:-not running}"

env: $(ENV_FILE)

$(ENV_FILE):
	@if [ ! -f $(ENV_EXAMPLE) ]; then \
		echo "ERROR: $(ENV_EXAMPLE) not found." >&2; exit 1; \
	fi
	@if ! command -v openssl >/dev/null 2>&1; then \
		echo "ERROR: openssl is required to generate random secrets." >&2; exit 1; \
	fi
	@cp $(ENV_EXAMPLE) $(ENV_FILE)
	@SECRET_KEY=$$(openssl rand -hex 32); \
	POSTGRES_PASSWORD=$$(openssl rand -hex 16); \
	ADMIN_PASSWORD=$$(openssl rand -hex 8); \
	POSTGRES_USER=$$(grep -E '^POSTGRES_USER=' $(ENV_FILE) | cut -d= -f2); \
	POSTGRES_DB=$$(grep -E '^POSTGRES_DB=' $(ENV_FILE) | cut -d= -f2); \
	sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$$SECRET_KEY|"                                                                                          $(ENV_FILE); \
	sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$$POSTGRES_PASSWORD|"                                                                      $(ENV_FILE); \
	sed -i "s|^DATABASE_URL=.*|DATABASE_URL=postgresql+asyncpg://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@postgres:5432/$${POSTGRES_DB}|"         $(ENV_FILE); \
	sed -i "s|^BOOTSTRAP_ADMIN_PASSWORD=.*|BOOTSTRAP_ADMIN_PASSWORD=$$ADMIN_PASSWORD|"                                                           $(ENV_FILE); \
	echo ""; \
	echo "  -> Created $(ENV_FILE) from $(ENV_EXAMPLE)."; \
	echo "  -> !!! RANDOM SECRETS WERE GENERATED. SAVE THEM NOW !!!"; \
	echo ""; \
	echo "       SECRET_KEY                = (32-byte hex, stored in $(ENV_FILE))"; \
	echo "       POSTGRES_PASSWORD         = $$POSTGRES_PASSWORD"; \
	echo "       BOOTSTRAP_ADMIN_PASSWORD  = $$ADMIN_PASSWORD"; \
	echo ""; \
	echo "  -> Admin login: user=admin  password=$$ADMIN_PASSWORD"; \
	echo ""; \
	echo "  -----------------------------------------------------------------"; \
	echo "  HuggingFace Token (HF_TOKEN)"; \
	echo "  -----------------------------------------------------------------"; \
	echo "  HF_TOKEN is used to download models from the HuggingFace Hub."; \
	echo "  Without it, only public models work. Gated/private models such"; \
	echo "  as Llama, Gemma or Mistral-Instruct will fail to download."; \
	echo ""; \
	echo "  How to obtain a token:"; \
	echo "    1. Sign in at https://huggingface.co/"; \
	echo "    2. Open https://huggingface.co/settings/tokens"; \
	echo "    3. Click 'Create new token', give it a name, choose the"; \
	echo "       'Read' role (enough to download models)"; \
	echo "    4. Copy the value — it starts with 'hf_...'"; \
	echo ""; \
	printf "  Paste your HF_TOKEN now (or press ENTER to skip): "; \
	if [ ! -t 0 ]; then \
		echo ""; \
		echo "  -> stdin is not a TTY, skipping. Edit HF_TOKEN in $(ENV_FILE) later."; \
	else \
		read -r HF_TOKEN_INPUT < /dev/tty; \
		if [ -n "$$HF_TOKEN_INPUT" ]; then \
			ESC_TOKEN=$$(printf '%s' "$$HF_TOKEN_INPUT" | sed -e 's/[\\&|]/\\&/g'); \
			sed -i "s|^HF_TOKEN=.*|HF_TOKEN=$$ESC_TOKEN|" $(ENV_FILE); \
			echo "  -> HF_TOKEN saved to $(ENV_FILE)."; \
		else \
			echo "  -> Skipped. HF_TOKEN still has placeholder - edit $(ENV_FILE) later."; \
		fi; \
	fi

gpu-override:
	@GPUS=$$(ls -1 /dev/nvidia[0-9]* 2>/dev/null | grep -E '^/dev/nvidia[0-9]+$$' | sort); \
	DEVICES=""; \
	for ctl in /dev/nvidiactl /dev/nvidia-uvm /dev/nvidia-uvm-tools; do \
		[ -e "$$ctl" ] && DEVICES="$$DEVICES $$ctl"; \
	done; \
	for g in $$GPUS; do DEVICES="$$DEVICES $$g"; done; \
	if [ -z "$$GPUS" ]; then \
		echo "  -> No /dev/nvidiaN devices found. Backend will start WITHOUT GPU passthrough."; \
	else \
		echo "  -> Detected GPUs:"; \
		for g in $$GPUS; do echo "       $$g"; done; \
	fi; \
	{ \
		echo "# Auto-generated by 'make gpu-override' — do not edit by hand."; \
		echo "# Regenerated on every 'make up'/'make gpu-override' from /dev/nvidia*."; \
		if [ -z "$$DEVICES" ]; then \
			echo "services: {}"; \
		else \
			echo "services:"; \
			echo "  backend:"; \
			echo "    devices:"; \
			for d in $$DEVICES; do echo "      - $$d:$$d"; done; \
		fi; \
	} > $(GPU_OVERRIDE_FILE)
	@echo "  -> Wrote $(GPU_OVERRIDE_FILE)"

resolve-ports:
	@if [ ! -x $(PORT_RESOLVER) ]; then chmod +x $(PORT_RESOLVER); fi
	@$(PORT_RESOLVER) $(COMPOSE_FILE)

clean:
	@if [ -f $(RESOLVED_FILE) ] && [ -f $(GPU_OVERRIDE_FILE) ]; then $(COMPOSE) down -v --remove-orphans; fi
	@rm -f $(RESOLVED_FILE) $(GPU_OVERRIDE_FILE)

nuke: clean
	-docker images --filter "reference=vllm_manager*" -q | xargs -r docker rmi -f
