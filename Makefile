.PHONY: install install-cutout cutout-model dev serve estado test lint fmt migrate preview clean

install:
	uv sync

# El recorte automatico, aparte: 369 MB de librerias. Quien no lo quiere, no los
# instala, y `passthrough` sigue siendo el proveedor por defecto.
install-cutout:
	uv sync --extra cutout

# El modelo son 177 MB que no viven en el repo. Se bajan una vez, a proposito y
# no en medio de la primera subida de alguien.
cutout-model:
	uv run --extra cutout python -c "from rembg import new_session; new_session('u2net'); print('u2net listo')"

dev:
	uv run uvicorn app.main:app --reload --port 8000

# Como se usa desde el telefono (ver README, «Despliegue»): sin --reload y solo
# en 127.0.0.1. A la red llega por `tailscale serve`; escuchar en 0.0.0.0
# abriria el puerto a quien comparta el wifi.
serve:
	uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# Que parte se cayo, en un paso: el servidor, Tailscale o el `serve`.
estado:
	@printf "servidor   "; curl -s -o /dev/null -w "%{http_code}\n" --max-time 3 http://127.0.0.1:8000/health || echo "no responde"
	@printf "tailscale  "; tailscale status --self --peers=false 2>&1 | head -1
	@echo "serve"; tailscale serve status 2>&1 | sed 's/^/  /'

# PYTHONDONTWRITEBYTECODE: el .pyc guarda el mtime del fuente en SEGUNDOS. Dos
# ediciones del mismo tamano dentro del mismo segundo (un script que cambia algo
# y lo revierte) dejan bytecode obsoleto que Python considera valido. Ver CLAUDE.md.
test:
	PYTHONDONTWRITEBYTECODE=1 uv run pytest

lint:
	uv run ruff check app tests
	uv run ruff format --check app tests

fmt:
	uv run ruff check --fix app tests
	uv run ruff format app tests

migrate:
	uv run python -m app.core.migrations

preview:
	uv run python -m app.domains.composition.preview $(ARGS)

clean:
	rm -rf .pytest_cache .ruff_cache htmlcov .coverage
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
