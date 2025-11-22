.PHONY: venv sync proto test docker-build docker-run docker-push-reg4

venv:
	uv venv

sync:
	uv sync

proto:
	python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. --pyi_out=. proto/bridge_sidecar.proto

test:
	uv run pytest tests/ -v

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
	@if [ -n "$(OUTPUT_FILE)" ]; then \
		echo "Using explicit OUTPUT_FILE=$(OUTPUT_FILE)"; \
	else \
		echo "OUTPUT_FILE not provided, default will be used"; \
	fi
	docker run --rm \
		-e REPO_URL="$(REPO_URL)" \
		-e COMMIT_HASH="$(COMMIT_HASH)" \
		-e AUTH_TOKEN="$(AUTH_TOKEN)" \
		$(if $(MODULE_PATH),-e MODULE_PATH="$(MODULE_PATH)") \
		$(if $(OUTPUT_FILE),-e OUTPUT_FILE="$(OUTPUT_FILE)") \
		bridge-sdk:latest

docker-push-reg4:
	@echo "Getting credentials from AWS Secrets Manager..."
	@SECRET=$$(aws --region us-east-2 secretsmanager get-secret-value --secret-id reg4-cred --output json --query SecretString --output text); \
	DOCKER_SERVER=$$(echo $$SECRET | sed -n 's/.*"docker-server":"\([^"]*\)".*/\1/p'); \
	DOCKER_USERNAME=$$(echo $$SECRET | sed -n 's/.*"docker-username":"\([^"]*\)".*/\1/p'); \
	DOCKER_PASSWORD=$$(echo $$SECRET | sed -n 's/.*"docker-password":"\([^"]*\)".*/\1/p'); \
	echo "Logging in to $$DOCKER_SERVER..."; \
	echo $$DOCKER_PASSWORD | docker login --username $$DOCKER_USERNAME --password-stdin $$DOCKER_SERVER; \
	echo "Tagging image..."; \
	docker tag bridge-sdk:latest $$DOCKER_SERVER/bridge/v1/sdk_analysis:latest; \
	echo "Pushing image to registry..."; \
	docker push $$DOCKER_SERVER/bridge/v1/sdk_analysis:latest

docker-build-and-push-reg4:
	make docker-build
	make docker-push-reg4