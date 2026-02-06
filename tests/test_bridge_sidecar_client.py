# Copyright 2026 Poolside, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for bridge_sidecar_client content_parts support."""

from concurrent import futures

import grpc
import pytest
from pydantic import ValidationError

from bridge_sdk.bridge_sidecar_client import (
    BridgeSidecarClient,
    to_proto_content_part,
)
from bridge_sdk.models import (
    ImageURLContent,
    ImageURLContentPart,
    TextContentPart,
)
from bridge_sdk.proto import bridge_sidecar_pb2, bridge_sidecar_pb2_grpc


# =============================================================================
# to_proto_content_part tests
# =============================================================================


class TestToProtoContentPart:
    def test_text_from_dict(self):
        part = to_proto_content_part({"type": "text", "text": "hello"})
        assert part.WhichOneof("content") == "text"
        assert part.text == "hello"

    def test_image_url_from_dict(self):
        part = to_proto_content_part(
            {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}}
        )
        assert part.WhichOneof("content") == "image_url"
        assert part.image_url.url == "https://example.com/img.png"

    def test_image_url_data_uri(self):
        data_uri = "data:image/png;base64,iVBORw0KGgo="
        part = to_proto_content_part(
            {"type": "image_url", "image_url": {"url": data_uri}}
        )
        assert part.image_url.url == data_uri

    def test_text_from_pydantic_model(self):
        part = to_proto_content_part(TextContentPart(type="text", text="from model"))
        assert part.WhichOneof("content") == "text"
        assert part.text == "from model"

    def test_image_url_from_pydantic_model(self):
        part = to_proto_content_part(
            ImageURLContentPart(
                type="image_url",
                image_url=ImageURLContent(url="https://example.com/pic.jpg"),
            )
        )
        assert part.WhichOneof("content") == "image_url"
        assert part.image_url.url == "https://example.com/pic.jpg"

    def test_passthrough_proto_object(self):
        proto = bridge_sidecar_pb2.ContentPart(text="already proto")
        result = to_proto_content_part(proto)
        assert result is proto

    def test_missing_type_raises(self):
        with pytest.raises(ValidationError):
            to_proto_content_part({"text": "no type"})

    def test_unsupported_type_raises(self):
        with pytest.raises(ValidationError):
            to_proto_content_part({"type": "audio", "data": "..."})

    def test_text_missing_text_raises(self):
        with pytest.raises(ValidationError):
            to_proto_content_part({"type": "text"})

    def test_text_empty_text_raises(self):
        with pytest.raises(ValidationError):
            to_proto_content_part({"type": "text", "text": ""})

    def test_image_url_missing_image_url_raises(self):
        with pytest.raises(ValidationError):
            to_proto_content_part({"type": "image_url"})

    def test_image_url_empty_url_raises(self):
        with pytest.raises(ValidationError):
            to_proto_content_part({"type": "image_url", "image_url": {"url": ""}})

    def test_non_dict_non_proto_raises(self):
        with pytest.raises(ValidationError):
            to_proto_content_part("not a dict")  # type: ignore


# =============================================================================
# BridgeSidecarClient.start_agent integration tests
# =============================================================================


class FakeSidecarServicer(bridge_sidecar_pb2_grpc.BridgeSidecarServiceServicer):
    """Records the request for assertion."""

    def __init__(self):
        self.last_request: bridge_sidecar_pb2.StartAgentRequest | None = None

    def StartAgent(self, request, context):
        self.last_request = request
        return bridge_sidecar_pb2.StartAgentResponse(
            run_detail=bridge_sidecar_pb2.RunDetail(
                agent_name=request.agent_name,
                session_id="test-session-id",
            ),
            exit_result="success",
        )


@pytest.fixture
def sidecar_server():
    """Start a real gRPC server with FakeSidecarServicer, yield (port, servicer)."""
    servicer = FakeSidecarServicer()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
    bridge_sidecar_pb2_grpc.add_BridgeSidecarServiceServicer_to_server(servicer, server)
    port = server.add_insecure_port("[::]:0")
    server.start()
    yield port, servicer
    server.stop(grace=0)


class TestStartAgentContentParts:
    def test_with_dict_content_parts(self, sidecar_server):
        port, servicer = sidecar_server
        with BridgeSidecarClient(port=port) as client:
            agent_name, session_id, exit_result = client.start_agent(
                prompt="describe this",
                agent_name="test-agent",
                directory="/tmp/work",
                content_parts=[
                    {"type": "text", "text": "What is in this image?"},
                    {"type": "image_url", "image_url": {"url": "https://example.com/img.png"}},
                ],
            )

        assert agent_name == "test-agent"
        assert session_id == "test-session-id"
        assert exit_result == "success"

        req = servicer.last_request
        assert req is not None
        assert len(req.content_parts) == 2
        assert req.content_parts[0].WhichOneof("content") == "text"
        assert req.content_parts[0].text == "What is in this image?"
        assert req.content_parts[1].WhichOneof("content") == "image_url"
        assert req.content_parts[1].image_url.url == "https://example.com/img.png"

    def test_with_proto_content_parts(self, sidecar_server):
        port, servicer = sidecar_server
        with BridgeSidecarClient(port=port) as client:
            client.start_agent(
                prompt="analyze",
                agent_name="test-agent",
                content_parts=[
                    bridge_sidecar_pb2.ContentPart(text="raw proto"),
                ],
            )

        req = servicer.last_request
        assert req is not None
        assert len(req.content_parts) == 1
        assert req.content_parts[0].text == "raw proto"

    def test_without_content_parts(self, sidecar_server):
        port, servicer = sidecar_server
        with BridgeSidecarClient(port=port) as client:
            client.start_agent(prompt="just text", agent_name="test-agent")

        req = servicer.last_request
        assert req is not None
        assert len(req.content_parts) == 0
        assert req.prompt == "just text"

    def test_empty_content_parts_list(self, sidecar_server):
        port, servicer = sidecar_server
        with BridgeSidecarClient(port=port) as client:
            client.start_agent(
                prompt="empty parts",
                agent_name="test-agent",
                content_parts=[],
            )

        req = servicer.last_request
        assert req is not None
        assert len(req.content_parts) == 0

    def test_not_connected_raises(self):
        client = BridgeSidecarClient()
        with pytest.raises(RuntimeError, match="Client not connected"):
            client.start_agent(
                prompt="fail",
                content_parts=[{"type": "text", "text": "should fail"}],
            )
