from enum import Enum
from typing import Annotated, Optional

from bridge_sdk import step, step_result
from bridge_sdk.bridge_sidecar_client import BridgeSidecarClient
from bridge_sdk.proto.bridge_sidecar_pb2 import ContinueFrom, RunDetail
from pydantic import BaseModel


class HelloWorldResult(BaseModel):
    session_id: str
    res: str


@step(
    setup_script="scripts/setup_test.sh",
    post_execution_script="scripts/post_execution_test.sh",
    metadata={"type": "agent"},
)
def hello_world_agent() -> HelloWorldResult:
    with BridgeSidecarClient() as client:
        _, session_id, res = client.start_agent("say hello", agent_name="Malibu")
        return HelloWorldResult(session_id=session_id, res=res)


class ContinuationInput(BaseModel):
    prompt: str


@step(
    setup_script="scripts/setup_test.sh",
    post_execution_script="scripts/post_execution_test.sh",
    metadata={"type": "agent"},
)
def continuation_agent(
    input: ContinuationInput,
    prev_result: Annotated[HelloWorldResult, step_result(hello_world_agent)],
) -> Optional[str]:
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
