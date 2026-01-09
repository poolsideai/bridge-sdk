"""Example pipeline module demonstrating Bridge SDK usage.

This module shows how to:
1. Define a Pipeline instance (exported as 'pipeline')
2. Define steps with @step decorator
3. Use step_result annotations to create dependencies between steps
"""

from typing import Annotated, Optional

from bridge_sdk import Pipeline, step, step_result
from bridge_sdk.bridge_sidecar_client import BridgeSidecarClient
from bridge_sdk.proto.bridge_sidecar_pb2 import ContinueFrom, RunDetail
from pydantic import BaseModel


# =============================================================================
# Pipeline Definition
# =============================================================================
# Each module can contain at most one Pipeline instance (any variable name).
# All @step decorated functions in this module will be associated with it.

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


class Step1Input(BaseModel):
    param1: str
    param2: int


class Step1Output(BaseModel):
    result: str


class Step2Input(BaseModel):
    param1: str
    param2: int


class Step2Output(BaseModel):
    result: str


# =============================================================================
# Steps
# =============================================================================


@step(
    setup_script="scripts/setup_test.sh",
    post_execution_script="scripts/post_execution_test.sh",
    metadata={"type": "agent"},
)
def hello_world_agent() -> HelloWorldResult:
    """First step: Start an agent session and say hello."""
    with BridgeSidecarClient() as client:
        _, session_id, res = client.start_agent("say hello", agent_name="Malibu")
        return HelloWorldResult(session_id=session_id, res=res)


@step(
    setup_script="scripts/setup_test.sh",
    post_execution_script="scripts/post_execution_test.sh",
    metadata={"type": "agent"},
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


@step
def step_1(input_data: Step1Input) -> Step1Output:
    """A simple step with no dependencies (root step)."""
    print(input_data)
    return Step1Output(result="done")


@step
def step2(
    input_data: Annotated[Step1Output, step_result(step_1)],
    some_other_param: Step2Input,
) -> Step2Output:
    """A step that depends on step_1 via step_result annotation."""
    print(input_data)
    print(some_other_param)
    return Step2Output(result="done")
