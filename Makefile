.PHONY: venv sync proto docker-build docker-run

venv:
	uv venv

sync:
	uv sync

proto:
	python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. --pyi_out=. proto/bridge_sidecar.proto

docker-build:
	docker build -t bridge-sdk:latest .

docker-run:
	@if [ -z "$(REPO_URL)" ]; then \
		echo "Error: REPO_URL is required. Usage: make docker-run REPO_URL=... COMMIT_HASH=... AUTH_TOKEN=... [MODULE_PATH=...]"; \
		echo "  Note: If MODULE_PATH is not provided, all modules in the repository will be discovered."; \
		exit 1; \
	fi
	@if [ -z "$(COMMIT_HASH)" ]; then \
		echo "Error: COMMIT_HASH is required. Usage: make docker-run REPO_URL=... COMMIT_HASH=... AUTH_TOKEN=... [MODULE_PATH=...]"; \
		echo "  Note: If MODULE_PATH is not provided, all modules in the repository will be discovered."; \
		exit 1; \
	fi
	@if [ -z "$(AUTH_TOKEN)" ]; then \
		echo "Error: AUTH_TOKEN is required. Usage: make docker-run REPO_URL=... COMMIT_HASH=... AUTH_TOKEN=... [MODULE_PATH=...]"; \
		echo "  Note: If MODULE_PATH is not provided, all modules in the repository will be discovered."; \
		exit 1; \
	fi
	@if [ -n "$(MODULE_PATH)" ]; then \
		echo "Running with MODULE_PATH=$(MODULE_PATH) (discovering steps from specific module)"; \
	else \
		echo "Running without MODULE_PATH (discovering all steps from all modules)"; \
	fi
	docker run --rm \
		-e REPO_URL="$(REPO_URL)" \
		-e COMMIT_HASH="$(COMMIT_HASH)" \
		-e AUTH_TOKEN="$(AUTH_TOKEN)" \
		$(if $(MODULE_PATH),-e MODULE_PATH="$(MODULE_PATH)") \
		bridge-sdk:latest