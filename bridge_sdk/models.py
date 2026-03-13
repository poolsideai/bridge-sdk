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

"""Pydantic models for the bridge sidecar client.

These exist alongside the generated proto messages to provide a friendlier
input interface for step authors. The proto ``ContentPart`` message works but
accepts any data without validation (empty strings, missing fields), only
failing on the Go sidecar with an unhelpful gRPC error. These models let
callers pass plain dicts and get immediate, descriptive validation errors.

Use whichever you prefer:
    - Dicts:    ``{"type": "text", "text": "..."}``
    - Models:   ``TextContentPart(type="text", text="...")``
    - Protos:   ``bridge_sidecar_pb2.ContentPart(text="...")``
"""

from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field, TypeAdapter, model_validator

from celpy import Environment as CelEnvironment
from celpy import celtypes

from bridge_sdk.proto import bridge_sidecar_pb2


class SandboxDefinition(BaseModel):
    """Defines an inline sandbox execution environment for a step.

    Allows pipeline authors to specify custom Docker images and resource
    requirements directly in the @step decorator instead of referencing
    a pre-existing sandbox definition by ID.

    Attributes:
        image: The Docker image to use for the sandbox (required).
        cpu_request: CPU request in Kubernetes format (e.g., '500m', '2').
        memory_request: Memory request in Kubernetes format (e.g., '512Mi', '2Gi').
        memory_limit: Memory limit in Kubernetes format (e.g., '1Gi', '4Gi').
        storage_request: Storage request in Kubernetes format (e.g., '10Gi').
        storage_limit: Storage limit in Kubernetes format (e.g., '50Gi').

    Example:
        @step(
            sandbox_definition=SandboxDefinition(
                image="python:3.11-slim",
                cpu_request="500m",
                memory_request="512Mi",
                memory_limit="1Gi",
            )
        )
        def my_step() -> str:
            return "executed in custom sandbox"
    """

    image: Optional[str] = None
    """The Docker image to use for the sandbox."""

    cpu_request: Optional[str] = None
    """CPU request in Kubernetes format (e.g., '500m', '2')."""

    memory_request: Optional[str] = None
    """Memory request in Kubernetes format (e.g., '512Mi', '2Gi')."""

    memory_limit: Optional[str] = None
    """Memory limit in Kubernetes format (e.g., '1Gi', '4Gi')."""

    storage_request: Optional[str] = None
    """Storage request in Kubernetes format (e.g., '10Gi')."""

    storage_limit: Optional[str] = None
    """Storage limit in Kubernetes format (e.g., '50Gi')."""


class WebhookPipelineAction(BaseModel):
    """Defines a webhook-triggered pipeline action.

    Webhook endpoints are configured in Console (signature verification,
    idempotency, secrets). The SDK only declares **actions** that reference
    an endpoint by name and define filtering/transformation logic via CEL.

    Attributes:
        name: Unique name for this webhook action within the pipeline + branch.
        branch: The git branch this webhook is indexed from and whose pipeline
            code runs when it fires.
        on: CEL expression evaluated against the payload and headers.
            Must return bool. The action triggers only when this evaluates to true.
        transform: CEL expression that transforms the payload into step inputs.
            Must return ``map(string, map(string, dyn))`` keyed by step name.
        webhook_endpoint: Name of the webhook endpoint configured in Console
            (e.g. ``"linear_issues"``).

    Example::

        from bridge_sdk import Pipeline, WebhookPipelineAction

        pipeline = Pipeline(
            name="on_issue_update",
            webhooks=[
                WebhookPipelineAction(
                    name="linear-issues",
                    branch="main",
                    on='payload.type == "Issue" && payload.action == "update"',
                    transform='{"triage_step": {"issue": payload.data}}',
                    webhook_endpoint="linear_issues",
                ),
            ],
        )
    """

    name: str
    """Unique name for this webhook action within the pipeline + branch."""

    branch: str
    """The git branch this webhook is indexed from and whose pipeline code runs when it fires."""

    on: str
    """CEL expression that determines whether this action should fire. Must return bool."""

    transform: str
    """CEL expression that transforms the payload into step inputs. Must return map(string, map(string, dyn))."""

    webhook_endpoint: str
    """Name of the webhook endpoint configured in Console."""

    @model_validator(mode="after")
    def _validate_cel_expressions(self) -> "WebhookPipelineAction":
        env = CelEnvironment(annotations={
            "payload": celtypes.Value,
            "headers": celtypes.MapType,
        })
        for field_name in ("on", "transform"):
            try:
                env.compile(getattr(self, field_name))
            except Exception as e:
                raise ValueError(
                    f"Invalid CEL expression in '{field_name}': {e}"
                ) from e
        return self


class ImageURLContent(BaseModel):
    url: str = Field(min_length=1)


class TextContentPart(BaseModel):
    type: Literal["text"]
    text: str = Field(min_length=1)

    def to_proto(self) -> bridge_sidecar_pb2.ContentPart:
        return bridge_sidecar_pb2.ContentPart(text=self.text)


class ImageURLContentPart(BaseModel):
    type: Literal["image_url"]
    image_url: ImageURLContent

    def to_proto(self) -> bridge_sidecar_pb2.ContentPart:
        return bridge_sidecar_pb2.ContentPart(
            image_url=bridge_sidecar_pb2.ImageURL(url=self.image_url.url)
        )


ContentPart = Annotated[
    Union[TextContentPart, ImageURLContentPart],
    Field(discriminator="type"),
]

ContentPartInput = ContentPart | bridge_sidecar_pb2.ContentPart | dict

content_part_adapter: TypeAdapter[ContentPart] = TypeAdapter(ContentPart)

def to_proto_content_part(part: ContentPartInput) -> bridge_sidecar_pb2.ContentPart:
    """Convert a dict, Pydantic model, or proto ContentPart to a proto ContentPart.

    Dicts and Pydantic models use OpenAI-style format::

        {"type": "text", "text": "..."}
        {"type": "image_url", "image_url": {"url": "..."}}

    Proto ``ContentPart`` messages are passed through unchanged.
    """
    if isinstance(part, bridge_sidecar_pb2.ContentPart):
        return part
    validated = content_part_adapter.validate_python(part)
    return validated.to_proto()

