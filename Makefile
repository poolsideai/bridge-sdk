.PHONY: venv sync proto docker-build

venv:
	uv venv

sync:
	uv sync

proto:
	python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. --pyi_out=. proto/bridge_sidecar.proto

docker-build:
	docker build -t bridge-sdk:latest .