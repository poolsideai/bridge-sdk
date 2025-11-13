from enum import Enum
from typing import Annotated, Optional

from lib import step, step_result
from lib.bridge_sidecar_client import BridgeSidecarClient
from proto.bridge_sidecar_pb2 import ContinueFrom, RunDetail

class AgentSteps(Enum):
    HELLO_WORLD_AGENT= "HelloWorld"
    CONTINUATION_AGENT="Continuation"

@step(
    name=AgentSteps.HELLO_WORLD_AGENT.value,
    setup_script="clone_repo.sh",
    post_execution_script="push_to_git.sh",
    metadata={
        "type": "agent"
    },
    depends_on=[]
)
def hello_world_agent() -> str:
    with BridgeSidecarClient() as client:
        _, session_id, res = client.start_agent("say hello", agent_name="agent_1003_cc_v2_rc-fp8-tpr")
        return session_id

@step(
    name=AgentSteps.CONTINUATION_AGENT.value,
    setup_script="clone_repo.sh",
    post_execution_script="push_to_git.sh",
    metadata={
        "type": "agent"
    },
    depends_on=[AgentSteps.HELLO_WORLD_AGENT.value]
)
def continuation_agent(prev_session_id: Annotated[str, step_result(AgentSteps.HELLO_WORLD_AGENT.value)]) -> Optional[str]:
    with BridgeSidecarClient() as client:
        _, session_id, res = client.start_agent(
            "tell me what was done previously",
            agent_name="agent_1003_cc_v2_rc-fp8-tpr",
            continue_from=ContinueFrom(
                previous_run_detail=RunDetail(
                    agent_name="agent_1003_cc_v2_rc-fp8-tpr",
                    session_id=prev_session_id
                ),
                continuation=ContinueFrom.NoCompactionStrategy()
            )
        )
        return session_id