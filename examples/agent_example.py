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

"""Example pipeline module demonstrating Bridge SDK usage.

This module shows how to:
1. Define a Pipeline instance (exported as 'pipeline')
2. Define steps with @pipeline.step decorator
3. Use step_result annotations to create dependencies between steps
"""

from typing import Annotated, Optional

from bridge_sdk import Pipeline, step_result
from bridge_sdk.bridge_sidecar_client import BridgeSidecarClient
from bridge_sdk.models import SandboxDefinition
from bridge_sdk.proto.bridge_sidecar_pb2 import ContinueFrom, RunDetail
from pydantic import BaseModel


# =============================================================================
# Pipeline Definition
# =============================================================================
# Each module can contain at most one Pipeline instance (any variable name).
# Use @pipeline.step to associate steps with this pipeline.

pipeline = Pipeline(
    name="agent_example",
    description="Example pipeline demonstrating agent steps with dependencies",
)


# =============================================================================
# Models
# =============================================================================

class HelloWorldResult(BaseModel):
    session_id: str
    res: str


class ContinuationInput(BaseModel):
    prompt: str

# =============================================================================
# Steps
# =============================================================================


@pipeline.step(
    setup_script="scripts/setup_test.sh",
    post_execution_script="scripts/post_execution_test.sh",
    metadata={"type": "agent"},
)
def hello_world_agent() -> HelloWorldResult:
    """First step: Start an agent session and say hello."""
    with BridgeSidecarClient() as client:
        _, session_id, res = client.start_agent("say hello", agent_name="Malibu")
        return HelloWorldResult(session_id=session_id, res=res)


@pipeline.step(
    setup_script="scripts/setup_test.sh",
    post_execution_script="scripts/post_execution_test.sh",
    metadata={"type": "agent"},
    sandbox_definition=SandboxDefinition(
        memory_limit="8Gi",
        memory_request="4Gi"
    )
)
def continuation_agent(
    input: ContinuationInput,
    prev_result: Annotated[HelloWorldResult, step_result(hello_world_agent)],
) -> Optional[str]:
    """Second step: Continue from the previous agent session.

    This step depends on hello_world_agent via the step_result annotation.
    The DAG is automatically inferred from this dependency.
    """
    with BridgeSidecarClient() as client:
        print(input)
        _, session_id, res = client.start_agent(
            "tell me what was done previously",
            agent_name="Malibu",
            continue_from=ContinueFrom(
                previous_run_detail=RunDetail(
                    agent_name="Malibu",
                    session_id=prev_result.session_id,
                ),
                continuation=ContinueFrom.NoCompactionStrategy(),
            ),
        )
        return session_id
