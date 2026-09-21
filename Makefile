SHELL = bash

DC_LOCAL = docker compose -f compose.base.yml -f compose.local.yml
DC_SERVER = docker compose -f compose.base.yml -f compose.server.yml

# --- Up / Down ---

up-local:
	$(DC_LOCAL) up -d

down-local:
	$(DC_LOCAL) down

up-server:
	$(DC_SERVER) up -d

down-server:
	$(DC_SERVER) down

reset-db:
	docker volume rm herbarium-platform_postgres_data || true

# --- Logs ---

logs-local:
	$(DC_LOCAL) logs -f

logs-server:
	$(DC_SERVER) logs -f

# --- PS ---

ps-local:
	@echo "LOCAL:"
	@$(DC_LOCAL) ps || true

ps-server:
	@echo "SERVER:"
	@$(DC_SERVER) ps || true

# --- Shards ---
# SUBPATH (optional): scan only this directory under IMAGE_DATA_PATH instead
# of the whole tree, e.g. make shards-prod SUBPATH=2023/09/21/new-batch

shards-local:
	python3 viewer/scripts/build_shards.py local $(SUBPATH)

shards-stage:
	python3 viewer/scripts/build_shards.py stage $(SUBPATH)

shards-prod:
	python3 viewer/scripts/build_shards.py prod $(SUBPATH)
