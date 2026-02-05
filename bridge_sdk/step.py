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

from typing import (
    Any,
    Callable,
    Dict,
    overload,
)
from typing_extensions import ParamSpec, TypeVar

from bridge_sdk.step_function import StepFunction, STEP_REGISTRY, make_step_function

P = ParamSpec("P")
R = TypeVar("R")


@overload
def step(
    func: Callable[P, R],
    *,
    name: str | None = None,
    rid: str | None = None,
    description: str | None = None,
    setup_script: str | None = None,
    post_execution_script: str | None = None,
    metadata: dict[str, Any] | None = None,
    sandbox_id: str | None = None,
    credential_bindings: dict[str, str] | None = None,
) -> StepFunction[P, R]:
    """Overload for usage as @step (no parentheses)."""
    ...


@overload
def step(
    *,
    name: str | None = None,
    rid: str | None = None,
    description: str | None = None,
    setup_script: str | None = None,
    post_execution_script: str | None = None,
    metadata: dict[str, Any] | None = None,
    sandbox_id: str | None = None,
    credential_bindings: dict[str, str] | None = None,
) -> Callable[[Callable[P, R]], StepFunction[P, R]]:
    """Overload for usage as @step(...)"""
    ...


def step(
    func: Callable[P, R] | None = None,
    *,
    name: str | None = None,
    rid: str | None = None,
    description: str | None = None,
    setup_script: str | None = None,
    post_execution_script: str | None = None,
    metadata: dict[str, Any] | None = None,
    sandbox_id: str | None = None,
    credential_bindings: dict[str, str] | None = None,
) -> StepFunction[P, R] | Callable[[Callable[P, R]], StepFunction[P, R]]:
    """Decorator for configuring a Step with execution metadata.

    Args:
        func: The function to decorate (when used without parentheses).
        name: Optional override name for the step. Defaults to function name.
        rid: Optional stable resource identifier (UUID). If provided, the backend
            will use this rid instead of generating a new one. This enables
            renaming steps while preserving their identity in the backend.
        description: Optional human-readable description.
        setup_script: Optional script to run before step execution.
        post_execution_script: Optional script to run after step execution.
        metadata: Optional arbitrary metadata dict.
        sandbox_id: Optional execution environment ID.
        credential_bindings: Optional credential name to ID mappings.

    Returns:
        A StepFunction wrapper with step_data and on_invoke_step attributes.
    """

    def _create_step_function(the_func: Callable[P, R]) -> StepFunction[P, R]:
        return make_step_function(
            the_func,
            name=name,
            rid=rid,
            description=description,
            setup_script=setup_script,
            post_execution_script=post_execution_script,
            metadata=metadata,
            sandbox_id=sandbox_id,
            credential_bindings=credential_bindings,
        )

    # If func is actually a callable, we were used as @step with no parentheses
    if callable(func):
        return _create_step_function(func)

    # Otherwise, we were used as @step(...), so return a decorator
    return _create_step_function


def get_dsl_output() -> Dict[str, Any]:
    """Generate DSL output from the step registry with type information."""
    return {
        step_name: step_func.step_data.model_dump(exclude_none=True)
        for step_name, step_func in STEP_REGISTRY.items()
    }
