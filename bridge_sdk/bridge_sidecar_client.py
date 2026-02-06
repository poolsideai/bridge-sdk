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

"""gRPC client for the Bridge service."""
import grpc
from typing import Optional
from bridge_sdk.proto import bridge_sidecar_pb2, bridge_sidecar_pb2_grpc


ContentPartInput = bridge_sidecar_pb2.ContentPart | dict


def _to_proto_content_part(part: ContentPartInput) -> bridge_sidecar_pb2.ContentPart:
    """Convert a dict or proto ContentPart to a proto ContentPart."""
    if isinstance(part, bridge_sidecar_pb2.ContentPart):
        return part
    if not isinstance(part, dict):
        raise TypeError(f"content_parts items must be dicts or ContentPart messages, got {type(part)}")
    part_type = part.get("type")
    if not part_type:
        raise ValueError("content_parts item must have a 'type' field")
    kwargs: dict = {"type": part_type}
    if part_type == "text":
        text = part.get("text")
        if not text:
            raise ValueError("text content part must have a non-empty 'text' field")
        kwargs["text"] = text
    elif part_type == "image_url":
        image_url = part.get("image_url")
        if not isinstance(image_url, dict) or not image_url.get("url"):
            raise ValueError("image_url content part must have an 'image_url' dict with a 'url' field")
        kwargs["image_url"] = bridge_sidecar_pb2.ImageURL(url=image_url["url"])
    else:
        raise ValueError(f"unsupported content part type: {part_type}")
    return bridge_sidecar_pb2.ContentPart(**kwargs)


class BridgeSidecarClient:
    """Client for communicating with the Bridge gRPC service."""

    def __init__(self, host: str = "localhost", port: int = 50052):
        """
        Initialize the Bridge client.

        Args:
            host: The hostname of the Bridge service
            port: The port of the Bridge service
        """
        self.address = f"{host}:{port}"
        self.channel: Optional[grpc.Channel] = None
        self.stub: Optional[bridge_sidecar_pb2_grpc.BridgeSidecarServiceStub] = None

    def connect(self):
        """Establish connection to the Bridge service."""
        self.channel = grpc.insecure_channel(self.address)
        self.stub = bridge_sidecar_pb2_grpc.BridgeSidecarServiceStub(self.channel)

    def close(self):
        """Close the connection to the Bridge service."""
        if self.channel:
            self.channel.close()

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def start_agent(
        self,
        prompt: str,
        agent_name: Optional[str] = None,
        directory: Optional[str] = None,
        continue_from: Optional[bridge_sidecar_pb2.ContinueFrom] = None,
        content_parts: Optional[list[ContentPartInput]] = None,
    ) -> tuple[str, str, str]:
        """
        Start an agent with the given prompt.

        Args:
            prompt: The prompt to provide to the agent
            agent_name: Name of the agent to use (defaults to "agent_1003_cc_v2_rc-fp8-tpr")
            directory: Working directory for the agent
            continue_from: Optional continuation details from a previous run
            content_parts: Optional multimodal content parts (text, images). Each item
                can be a dict like ``{"type": "text", "text": "..."}`` or
                ``{"type": "image_url", "image_url": {"url": "..."}}`` or a proto
                ``ContentPart`` message directly.

        Returns:
            Tuple of (agent_name, session_id, exit_result)
        """
        if not self.stub:
            raise RuntimeError("Client not connected. Call connect() first.")

        if agent_name is None:
            agent_name = "agent_1003_cc_v2_rc-fp8-tpr"

        proto_parts = [_to_proto_content_part(p) for p in content_parts] if content_parts else []

        request = bridge_sidecar_pb2.StartAgentRequest(
            prompt=prompt,
            agent_name=agent_name,
            directory=directory or "",
            continue_from=continue_from,
            content_parts=proto_parts,
        )
        response = self.stub.StartAgent(request)

        return (
            response.run_detail.agent_name,
            response.run_detail.session_id,
            response.exit_result,
        )