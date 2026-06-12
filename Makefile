.PHONY: infra server web dev test test-server lint image image-flutter stop

infra:
	docker compose up -d redis

server: infra
	cd server && uv run uvicorn tremblecode_server.main:app --host 0.0.0.0 --port 8400 --reload

web:
	cd web && pnpm dev

# Run infra + server + web together (Ctrl-C stops all)
dev: infra
	$(MAKE) -j2 _dev-server _dev-web

_dev-server:
	cd server && uv run uvicorn tremblecode_server.main:app --host 0.0.0.0 --port 8400 --reload

_dev-web:
	cd web && pnpm dev

test: test-server

test-server:
	cd server && uv run pytest -q

lint:
	cd web && pnpm lint

image:
	docker build -t tremblecode-sandbox:base -f sandbox/image/Dockerfile sandbox

image-flutter: image
	docker build -t tremblecode-sandbox:flutter -f sandbox/image/Dockerfile.flutter sandbox

stop:
	docker compose down
