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
	@echo "Note: Required variables (REPO_URL, BRANCH_NAME, AUTH_TOKEN) can be provided via:"; \
	echo "  - Command line: make docker-run REPO_URL=... BRANCH_NAME=... AUTH_TOKEN=... [COMMIT_HASH=...]"; \
	echo "  - .env file: Variables will be loaded from .env if it exists"; \
	echo "  - Environment: Variables can be set in your shell environment"; \
	echo "  - COMMIT_HASH is optional - if not provided, latest commit on branch will be used"
	@if [ -n "$(MODULE_PATH)" ]; then \
		echo "Running with MODULE_PATH=$(MODULE_PATH) (discovering steps from specific module)"; \
	else \
		echo "Running without MODULE_PATH (discovering all steps from all modules)"; \
	fi
	@if [ -n "$(DSL_OUTPUT_FILE)" ]; then \
		echo "Using explicit DSL_OUTPUT_FILE=$(DSL_OUTPUT_FILE)"; \
	elif [ -n "$(OUTPUT_FILE)" ]; then \
		echo "Using explicit OUTPUT_FILE=$(OUTPUT_FILE)"; \
	else \
		echo "DSL_OUTPUT_FILE/OUTPUT_FILE not provided, default will be used"; \
	fi
	@if [ -n "$(COMMIT_HASH)" ]; then \
		echo "Using explicit COMMIT_HASH=$(COMMIT_HASH)"; \
	else \
		echo "COMMIT_HASH not provided, will use latest commit on branch"; \
	fi
	@if [ -f .env ]; then \
		echo "Loading environment variables from .env file..."; \
		ENV_FILE_FLAG="--env-file .env"; \
	else \
		ENV_FILE_FLAG=""; \
	fi; \
	docker run --rm \
		$$ENV_FILE_FLAG \
		$(if $(REPO_URL),-e REPO_URL="$(REPO_URL)") \
		$(if $(BRANCH_NAME),-e BRANCH_NAME="$(BRANCH_NAME)") \
		$(if $(COMMIT_HASH),-e COMMIT_HASH="$(COMMIT_HASH)") \
		$(if $(AUTH_TOKEN),-e AUTH_TOKEN="$(AUTH_TOKEN)") \
		$(if $(MODULE_PATH),-e MODULE_PATH="$(MODULE_PATH)") \
		$(if $(DSL_OUTPUT_FILE),-e DSL_OUTPUT_FILE="$(DSL_OUTPUT_FILE)") \
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