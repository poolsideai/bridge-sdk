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

"""Tests for bridge_execution_client content_parts and transport support."""

from concurrent import futures
import importlib
import sys
import warnings

import grpc
import pytest
from pydantic import ValidationError

from bridge_sdk.bridge_execution_client import BridgeExecutionClient
from bridge_sdk.models import (
    ImageURLContent,
    ImageURLContentPart,
    TextContentPart,
    to_proto_content_part,
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
# BridgeExecutionClient.start_agent integration tests
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
        with BridgeExecutionClient(port=port) as client:
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
        with BridgeExecutionClient(port=port) as client:
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
        with BridgeExecutionClient(port=port) as client:
            client.start_agent(prompt="just text", agent_name="test-agent")

        req = servicer.last_request
        assert req is not None
        assert len(req.content_parts) == 0
        assert req.prompt == "just text"

    def test_empty_content_parts_list(self, sidecar_server):
        port, servicer = sidecar_server
        with BridgeExecutionClient(port=port) as client:
            client.start_agent(
                prompt="empty parts",
                agent_name="test-agent",
                content_parts=[],
            )

        req = servicer.last_request
        assert req is not None
        assert len(req.content_parts) == 0

    def test_not_connected_raises(self):
        client = BridgeExecutionClient()
        with pytest.raises(RuntimeError, match="Client not connected"):
            client.start_agent(
                prompt="fail",
                content_parts=[{"type": "text", "text": "should fail"}],
            )


class FakeSessionsBridgeClient(BridgeExecutionClient):
    def __init__(
        self,
        *,
        sessions_async: bool = False,
        session_states: list[str] | None = None,
        sessions_wait_timeout_seconds: float = 1.0,
        sessions_poll_interval_seconds: float = 0.001,
    ):
        super().__init__(
            agent_transport="sessions",
            api_base_url="https://api.example.com",
            api_token="token",
            sandbox_id="sandbox-123",
            sessions_async=sessions_async,
            sessions_wait_timeout_seconds=sessions_wait_timeout_seconds,
            sessions_poll_interval_seconds=sessions_poll_interval_seconds,
        )
        self.calls: list[dict] = []
        self._session_states = session_states or ["finished"]
        self._session_state_idx = 0

    def _sessions_request_json(self, method, path, *, query=None, body=None):
        self.calls.append(
            {
                "method": method,
                "path": path,
                "query": query,
                "body": body,
            }
        )
        if method == "GET" and path == "/v0/agents":
            assert query == {"name": "Malibu"}
            return [{"id": "agent-123", "name": "Malibu"}]
        if method == "POST" and path == "/v0/agents/agent-123/sessions":
            return {"id": "session-456"}
        if method == "GET" and path == "/v0/sessions/session-456":
            idx = min(self._session_state_idx, len(self._session_states) - 1)
            self._session_state_idx += 1
            return {"id": "session-456", "state": self._session_states[idx]}
        raise AssertionError(f"unexpected request: {method} {path}")


class TestStartAgentSessionsTransport:
    def test_requires_sessions_config(self):
        client = BridgeExecutionClient(agent_transport="sessions")
        with pytest.raises(
            RuntimeError, match="sessions transport requires BRIDGE_SDK_API_BASE_URL"
        ):
            client.start_agent(prompt="hello")

    def test_starts_session_without_continue_from(self):
        client = FakeSessionsBridgeClient()
        agent_name, session_id, exit_result = client.start_agent(
            prompt="say hello",
            agent_name="Malibu",
        )

        assert agent_name == "Malibu"
        assert session_id == "session-456"
        assert exit_result == "success"

        assert len(client.calls) == 3
        assert client.calls[1]["body"] == {
            "type": "remote",
            "prompt": "say hello",
            "sandbox_id": "sandbox-123",
        }
        assert client.calls[2] == {
            "method": "GET",
            "path": "/v0/sessions/session-456",
            "query": None,
            "body": None,
        }

    def test_maps_continue_from_no_compaction(self):
        continue_from = bridge_sidecar_pb2.ContinueFrom(
            previous_run_detail=bridge_sidecar_pb2.RunDetail(
                agent_name="Malibu",
                session_id="previous-session-1",
            ),
            continuation=bridge_sidecar_pb2.ContinueFrom.NoCompactionStrategy(),
        )
        client = FakeSessionsBridgeClient()
        client.start_agent(
            prompt="continue",
            agent_name="Malibu",
            continue_from=continue_from,
        )

        assert len(client.calls) == 3
        assert client.calls[1]["body"]["continue_from"] == {
            "previous_session_id": "previous-session-1",
            "strategy": "no_compaction",
        }

    def test_async_mode_returns_scheduled_without_waiting(self):
        client = FakeSessionsBridgeClient(sessions_async=True)
        _, _, exit_result = client.start_agent(
            prompt="say hello",
            agent_name="Malibu",
        )

        assert exit_result == "scheduled"
        assert len(client.calls) == 2

    def test_returns_failure_when_terminal_state_is_failed(self):
        client = FakeSessionsBridgeClient(
            session_states=["starting", "running", "failed"]
        )
        _, _, exit_result = client.start_agent(
            prompt="say hello",
            agent_name="Malibu",
        )

        assert exit_result == "failure"
        assert [c["path"] for c in client.calls[2:]] == [
            "/v0/sessions/session-456",
            "/v0/sessions/session-456",
            "/v0/sessions/session-456",
        ]

    def test_wait_timeout_raises(self):
        client = FakeSessionsBridgeClient(
            session_states=["starting"],
            sessions_wait_timeout_seconds=0.01,
            sessions_poll_interval_seconds=0.005,
        )
        with pytest.raises(RuntimeError, match="timed out waiting for session"):
            client.start_agent(
                prompt="say hello",
                agent_name="Malibu",
            )

    def test_rejects_continue_from_compaction(self):
        continue_from = bridge_sidecar_pb2.ContinueFrom(
            previous_run_detail=bridge_sidecar_pb2.RunDetail(
                agent_name="Malibu",
                session_id="previous-session-1",
            ),
            compaction=bridge_sidecar_pb2.ContinueFrom.CompactionStrategy(),
        )
        client = FakeSessionsBridgeClient()
        with pytest.raises(ValueError, match="compaction is not supported"):
            client.start_agent(
                prompt="continue",
                agent_name="Malibu",
                continue_from=continue_from,
            )

    def test_rejects_content_parts_and_directory(self):
        client = FakeSessionsBridgeClient()
        with pytest.raises(ValueError, match="content_parts are not supported"):
            client.start_agent(
                prompt="continue",
                agent_name="Malibu",
                content_parts=[{"type": "text", "text": "x"}],
            )
        with pytest.raises(ValueError, match="directory is not supported"):
            client.start_agent(
                prompt="continue",
                agent_name="Malibu",
                directory="/tmp/work",
            )


def test_bridge_sidecar_client_shim_warns_and_reexports():
    module_name = "bridge_sdk.bridge_sidecar_client"
    if module_name in sys.modules:
        del sys.modules[module_name]

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always", DeprecationWarning)
        module = importlib.import_module(module_name)

    assert any(
        "deprecated" in str(w.message).lower() and w.category is DeprecationWarning
        for w in captured
    )
    assert module.BridgeExecutionClient is BridgeExecutionClient
    assert module.BridgeSidecarClient is BridgeExecutionClient
