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

"""StepFunction class and step registry."""

import inspect
import json
from functools import update_wrapper
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
)

from pydantic import TypeAdapter, ValidationError
from typing_extensions import ParamSpec, TypeVar

from bridge_sdk.exceptions import StepError
from bridge_sdk.function_schema import FunctionSchema, create_function_schema
from bridge_sdk.logger import logger
from bridge_sdk.models import SandboxDefinition
from bridge_sdk.step_data import StepData, create_step_data

STEP_REGISTRY: Dict[str, "StepFunction[..., Any]"] = {}

P = ParamSpec("P")
R = TypeVar("R")


class StepFunction(Generic[P, R]):
    """A callable wrapper for step-decorated functions.

    Wraps a function decorated with @step, providing access to step metadata
    and invocation capabilities while preserving the original function's
    call signature.
    """

    def __init__(
        self,
        func: Callable[P, R],
        schema: FunctionSchema,
        step_data: StepData,
    ):
        self._func = func
        self._schema = schema
        self.step_data = step_data
        update_wrapper(self, func)

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R:
        return self._func(*args, **kwargs)

    async def on_invoke_step(self, input: str, step_results: str) -> str:
        """Invoke the step with JSON input and return JSON output.

        Args:
            input: JSON string of input parameters.
            step_results: JSON string of results from previous steps.

        Returns:
            JSON string of the function's return value.
        """
        try:
            input_data: dict[str, Any] = json.loads(input) if input else {}
        except Exception as e:
            raise StepError(
                f"Invalid JSON input for step {self._schema.name}: {input}"
            ) from e

        try:
            step_results_data: dict[str, Any] = (
                json.loads(step_results) if step_results else {}
            )
        except Exception as e:
            raise StepError(
                f"Invalid JSON step results for step {self._schema.name}: {step_results}"
            ) from e

        # If a cached result exists, use it in place of the input
        for param_name, step_name in self.step_data.params_from_step_results.items():
            if step_name in step_results_data:
                input_data[param_name] = step_results_data[step_name]

        try:
            parsed = (
                self._schema.params_pydantic_model(**input_data)
                if input_data
                else self._schema.params_pydantic_model()
            )
        except ValidationError as e:
            raise StepError(
                f"Invalid JSON input for step {self._schema.name}: {e}"
            ) from e

        kwargs = dict(parsed)

        # Type checker can't verify dynamic kwargs match P, but Pydantic validation ensures correctness
        if inspect.iscoroutinefunction(self._func):
            result = await self._func(**kwargs)  # type: ignore[arg-type]
        else:
            result = self._func(**kwargs)  # type: ignore[arg-type]

        logger.debug(f"Step {self.step_data.name} completed.")

        # Serialize the result to JSON
        try:
            return_type = (
                str
                if self._schema.return_type in (Any, None)
                else self._schema.return_type
            )
            return TypeAdapter(return_type).dump_json(result).decode()
        except (ValueError, TypeError) as e:
            raise StepError(
                f"Failed to serialize return value for step {self.step_data.name}: {e}"
            ) from e



def make_step_function(
    the_func: Callable[P, R],
    *,
    name: str | None = None,
    rid: str | None = None,
    description: str | None = None,
    setup_script: str | None = None,
    post_execution_script: str | None = None,
    metadata: dict[str, Any] | None = None,
    sandbox_id: str | None = None,
    credential_bindings: dict[str, str] | None = None,
    pipeline_name: str | None = None,
    sandbox_definition: SandboxDefinition | None = None,
) -> StepFunction[P, R]:
    """Create a StepFunction, register it, and return it.

    This is the shared implementation used by both the module-level @step
    decorator and Pipeline.step().
    """
    schema = create_function_schema(func=the_func)

    data = create_step_data(
        func=the_func,
        function_schema=schema,
        name=name,
        rid=rid,
        description=description,
        setup_script=setup_script,
        post_execution_script=post_execution_script,
        metadata=metadata,
        sandbox_id=sandbox_id,
        credential_bindings=credential_bindings,
        pipeline_name=pipeline_name,
        sandbox_definition=sandbox_definition,
    )

    step_function = StepFunction(the_func, schema, data)
    STEP_REGISTRY[data.name] = step_function
    return step_function
