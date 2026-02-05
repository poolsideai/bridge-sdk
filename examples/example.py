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

from typing import Annotated

from bridge_sdk import step, step_result
from bridge_sdk.bridge_sidecar_client import BridgeSidecarClient
from pydantic import BaseModel


# Pydantic models for step inputs and outputs
class Step1Input(BaseModel):
    value: str


class Step1Output(BaseModel):
    result: str


@step(
    setup_script="scripts/setup_test.sh",
    post_execution_script="scripts/post_execution_test.sh",
    metadata={"type": "agent"},
)
def step_1(input_data: Step1Input) -> Step1Output:
    print(input_data.value)
    return Step1Output(result="transformed")


class Step2Input(BaseModel):
    value: str


class Step2Output(BaseModel):
    result: str


@step(
    name="step_2_override",
    setup_script="scripts/setup_test.sh",
    post_execution_script="scripts/post_execution_test.sh",
    metadata={"type": "agent"},
)
def step_2(
    input_data: Step2Input,
    step_1_result: Annotated[Step1Output, step_result(step_1), "some_annotation"],
) -> Step2Output:
    print("This was the output of step 1", step_1_result.result)
    return Step2Output(result=input_data.value)


class Step3Input(BaseModel):
    value: str


class Step3Output(BaseModel):
    result: str


@step(
    setup_script="scripts/setup_test.sh",
    post_execution_script="scripts/post_execution_test.sh",
)
def step_3(
    input_data: Step3Input,
    step_2_result: Annotated[Step2Output, step_result(step_2)],
) -> Step3Output:
    print("This was the output of step 2:", step_2_result.result)
    return Step3Output(result=input_data.value)


class Step4Input(BaseModel):
    value: str


class Step4Output(BaseModel):
    result: str


@step(
    setup_script="clone_repo.sh",
    post_execution_script="push_to_git.sh",
    metadata={"type": "agent"},
)
def step_4(
    input_data: Step4Input,
    step_2_result: Annotated[Step2Output, step_result(step_2)],
) -> Step4Output:
    print("This was the output of step 2:", step_2_result.result)
    with BridgeSidecarClient() as client:
        res = client.start_agent("say hello", agent_name="agent_1003_cc_v2_rc-fp8-tpr")
        print(res)
    return Step4Output(result=input_data.value)
