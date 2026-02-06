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

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter

from bridge_sdk.proto import bridge_sidecar_pb2


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

content_part_adapter = TypeAdapter(ContentPart)

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

