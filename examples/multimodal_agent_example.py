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

"""Example pipeline demonstrating multimodal content parts."""

from typing import Annotated

from bridge_sdk import Pipeline, step_result
from bridge_sdk.bridge_sidecar_client import BridgeSidecarClient
from bridge_sdk.proto.bridge_sidecar_pb2 import ContinueFrom, RunDetail
from pydantic import BaseModel


pipeline = Pipeline(
    name="multimodal_agent_example",
    description="Example pipeline using text and image content parts",
)


class AnalyzeImageResult(BaseModel):
    session_id: str
    res: str


class FollowupInput(BaseModel):
    prompt: str


@pipeline.step(metadata={"type": "agent"})
def analyze_image() -> AnalyzeImageResult:
    """Start an agent session with text and image content parts."""
    content_parts = [
        {"type": "text", "text": "Describe the image and list notable objects."},
        {
            "type": "image_url",
            "image_url": {
                "url": "https://upload.wikimedia.org/wikipedia/commons/7/70/Example.png"
            },
        },
    ]

    with BridgeSidecarClient() as client:
        _, session_id, res = client.start_agent(
            prompt="Analyze the attached image.",
            agent_name="Malibu",
            content_parts=content_parts,
        )
        return AnalyzeImageResult(session_id=session_id, res=res)


@pipeline.step(metadata={"type": "agent"})
def followup(
    input: FollowupInput,
    previous: Annotated[AnalyzeImageResult, step_result(analyze_image)],
) -> str:
    """Continue the conversation using the previous session id."""
    with BridgeSidecarClient() as client:
        _, _, res = client.start_agent(
            prompt=input.prompt,
            agent_name="Malibu",
            continue_from=ContinueFrom(
                previous_run_detail=RunDetail(
                    agent_name="Malibu",
                    session_id=previous.session_id,
                ),
                continuation=ContinueFrom.NoCompactionStrategy(),
            ),
        )
        return res
