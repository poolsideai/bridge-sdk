.PHONY: venv sync proto test docker-build docker-run docker-push-reg4

TAG ?= latest

venv:
	uv venv

sync:
	uv sync

proto:
	python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. --pyi_out=. proto/bridge_sidecar.proto

test:
	uv run pytest tests/ -v