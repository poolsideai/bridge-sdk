import inspect
import json
from typing import (
    Any,
    Callable,
    Dict,
    TypeVar,
    overload,
)
from pydantic import TypeAdapter, ValidationError
from typing_extensions import ParamSpec

from lib.exceptions import StepError
from lib.function_schema import FunctionSchema, create_function_schema
from lib.logger import logger
from lib.step_data import StepData, create_step_data

STEP_REGISTRY: Dict[str, Callable[..., Any]] = {}

async def invoke_step(
    func: Callable[..., Any],
    schema: FunctionSchema,
    data: StepData,
    input: str,
    step_results: str,
) -> str:
    """Invoke a step function with JSON input and return JSON output.

    Args:
        func: The step function to invoke.
        schema: The function schema for validation and serialization.
        data: The step data containing metadata.
        input: JSON string of input parameters.
        step_results: JSON string of results from previous steps.

    Returns:
        JSON string of the function's return value.
    """
    try:
        input_json_data: dict[str, Any] = json.loads(input) if input else {}
    except Exception as e:
        raise StepError(
            f"Invalid JSON input for step {schema.name}: {input}"
        ) from e

    try:
        step_results_json_data: dict[str, Any] = (
            json.loads(step_results) if step_results else {}
        )
    except Exception as e:
        raise StepError(
            f"Invalid JSON step results for step {schema.name}: {step_results}"
        ) from e

    # If a cached result exists, use it in place of the input
    for param_name, step_name in data.params_from_step_results.items():
        if step_name in step_results_json_data:
            input_json_data[param_name] = step_results_json_data[step_name]

    try:
        parsed = (
            schema.params_pydantic_model(**input_json_data)
            if input_json_data
            else schema.params_pydantic_model()
        )
    except ValidationError as e:
        raise StepError(
            f"Invalid JSON input for step {schema.name}: {e}"
        ) from e

    kwargs = dict(parsed)

    if inspect.iscoroutinefunction(func):
        result = await func(**kwargs)
    else:
        result = func(**kwargs)

    logger.debug(f"Step {data.name} completed.")

    # Serialize the result to JSON
    try:
        # We assume the return type is a string if no return type is available on the schema
        return_type = str if schema.return_type in (Any, None) else schema.return_type
        return TypeAdapter(return_type).dump_json(result).decode()
    except (ValueError, TypeError) as e:
        raise StepError(
            f"Failed to serialize return value for step {data.name}: {e}"
        ) from e

P = ParamSpec("P")
R = TypeVar("R")

@overload
def step(
    func: Callable[P, R],
    *,
    name: str | None = None,
    description: str | None = None,
    setup_script: str | None = None,
    post_execution_script: str | None = None,
    metadata: dict[str, Any] | None = None,
    sandbox_id: str | None = None,
) -> Callable[P, R]:
    """Overload for usage as @step (no parentheses)."""
    ...


@overload
def step(
    *,
    name: str | None = None,
    description: str | None = None,
    setup_script: str | None = None,
    post_execution_script: str | None = None,
    metadata: dict[str, Any] | None = None,
    sandbox_id: str | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Overload for usage as @step(...)"""
    ...


def step(
    func: Callable[P, R] | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    setup_script: str | None = None,
    post_execution_script: str | None = None,
    metadata: dict[str, Any] | None = None,
    sandbox_id: str | None = None,
) -> Callable[P, R] | Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator for configuring a Step with execution metadata.

    Returns the original function with step attributes attached.
    Access step metadata via `func.step_data` and `func.on_invoke_step`.
    """

    def _create_step(the_func: Callable[P, R]) -> Callable[P, R]:
        schema = create_function_schema(func=the_func)

        data = create_step_data(
            func=the_func,
            function_schema=schema,
            name=name,
            description=description,
            setup_script=setup_script,
            post_execution_script=post_execution_script,
            metadata=metadata,
            sandbox_id=sandbox_id,
        )

        async def on_invoke_step(input: str, step_results: str) -> str:
            return await invoke_step(the_func, schema, data, input, step_results)

        # Attach step attributes directly to the function
        the_func.step_data = data  # type: ignore[attr-defined]
        the_func.on_invoke_step = on_invoke_step  # type: ignore[attr-defined]

        STEP_REGISTRY[data.name] = the_func

        return the_func

    # If func is actually a callable, we were used as @step with no parentheses
    if callable(func):
        return _create_step(func)

    # Otherwise, we were used as @step(...), so return a decorator
    return _create_step


def get_dsl_output() -> Dict[str, Any]:
    """Generate DSL output from the step registry with type information."""
    return {
        step_name: step_func.step_data.model_dump(exclude_none=True)  # type: ignore[attr-defined]
        for step_name, step_func in STEP_REGISTRY.items()
    }