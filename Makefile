.PHONY: venv sync proto test docker-build docker-run docker-push-reg4

TAG ?= latest

venv:
	uv venv

sync:
	uv sync

proto:
	python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. --pyi_out=. bridge_sdk/proto/bridge_sidecar.proto
	# Fix import path and module references in generated gRPC file
	sed -i '' 's/^from bridge_sdk\.proto import bridge_sidecar_pb2 as bridge__sdk_dot_proto_dot_bridge__sidecar__pb2/from bridge_sdk.proto import bridge_sidecar_pb2/' bridge_sdk/proto/bridge_sidecar_pb2_grpc.py
	sed -i '' 's/bridge__sdk_dot_proto_dot_bridge__sidecar__pb2/bridge_sidecar_pb2/g' bridge_sdk/proto/bridge_sidecar_pb2_grpc.py

test:
	uv run pytest tests/ -v