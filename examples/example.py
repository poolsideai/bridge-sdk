from enum import Enum
from typing import Annotated

from lib import step, step_result, STEP_INPUT
from lib.bridge_sidecar_client import BridgeSidecarClient


class Steps(Enum):
    STEP_1="Step1"
    STEP_2="Step2"
    STEP_3="Step3"

@step(
    name=Steps.STEP_1.value,
    setup_script="clone_repo.sh",
    post_execution_script="push_to_git.sh",
    metadata={
        "type": "agent"
    },
    depends_on=[]
)
def step_1(input_data: Annotated[str, STEP_INPUT]) -> str:
    print(input_data)
    return "transformed"


@step(
    name=Steps.STEP_2.value,
    setup_script="clone_repo.sh",
    post_execution_script="push_to_git.sh",
    metadata={
        "type": "agent"
    },
    depends_on=[Steps.STEP_1.value]
)
def step_2(input_data: Annotated[str, STEP_INPUT], step_1_result: Annotated[str, step_result(Steps.STEP_1.value)]) -> str:
        print("This was the output of step 1", step_1_result)
        return input_data

@step(
    name=Steps.STEP_3.value,
    setup_script="clone_repo.sh",
    post_execution_script="push_to_git.sh",
    metadata={
        "type": "agent"
    },
    depends_on=[Steps.STEP_2.value]
)
def step_3(input_data: Annotated[str, STEP_INPUT], step2_result: Annotated[str, step_result(Steps.STEP_2.value)]) -> str:
    print("This was the output of step 2:", step2_result)
    with BridgeSidecarClient() as client:
        res = client.start_agent("say hello", agent_name="agent_1003_cc_v2_rc-fp8-tpr")
        print(res)
    return input_data