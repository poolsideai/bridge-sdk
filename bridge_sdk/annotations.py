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

from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from bridge_sdk.step_function import StepFunction

STEP_RESULT_PREFIX = "step:"


def step_result(step: "str | StepFunction[..., Any]") -> str:
    """Create a step_result annotation.

    Args:
        step: Either a step name (str) or a @step-decorated function. If a decorated
              function is provided, the step's actual name will be used (which is the
              function name if no override was provided, or the override name if
              @step(name=...) was used).

    Returns:
        A string annotation in the format "step:step_name"
    """
    if isinstance(step, str):
        step_name = step
    else:
        step_name = step.step_data.name

    return f"{STEP_RESULT_PREFIX}{step_name}"


def extract_step_result_annotation(annotations: tuple[Any, ...]) -> Optional[str]:
    for annotation in annotations:
        if isinstance(annotation, str) and annotation.startswith(STEP_RESULT_PREFIX):
            return annotation[len(STEP_RESULT_PREFIX):].strip()
    return None