from dataclasses import dataclass
import inspect
import json
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    overload,
)
from pydantic import ValidationError
from typing_extensions import ParamSpec

from lib.exceptions import StepError
from lib.function_schema import function_schema
from lib.logger import logger
from lib.step_data import StepData, step_data
from lib.utils import get_relative_path

StepParams = ParamSpec("StepParams")
StepFunction = Callable[StepParams, Any]


@dataclass
class Step:
    step_data: StepData
    """The step data to be used in Bridge."""
    on_invoke_step: Callable[[str, str], Awaitable[str]]
    """A function that invokes the step with the given parameters.
    This is called when a step is executed through the bridge CLI.
    The arguments are to be passed as a json string.
    Returns a JSON string representation of the result.
    """
    _original_func: Callable[..., Any]
    """The original function that was decorated. Used for direct invocation."""

    def __call__(self, *args, **kwargs):
        """Allow direct invocation of the step function.

        We use a wrapper class (rather than attaching attributes to the original
        function) to enable future interception of step invocations (logging,
        API calls, etc). When adding async interception, this may need to branch
        on iscoroutinefunction to handle sync vs async invocation differently.
        """
        return self._original_func(*args, **kwargs)


STEP_REGISTRY: Dict[str, Step] = {}


@overload
def step(
    func: StepFunction[...],
    *,
    name: str | None = None,
    description: str | None = None,
    setup_script: str | None = None,
    post_execution_script: str | None = None,
    metadata: dict[str, Any] | None = None,
    sandbox_id: str | None = None,
    depends_on: list[str | Step] | None = None,
) -> StepFunction[...]:
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
    depends_on: list[str | Step] | None = None,
) -> Callable[[StepFunction[...]], StepFunction[...]]:
    """Overload for usage as @step(...)"""
    ...


def step(
    func: StepFunction[...] | None = None,
    *,
    name: str | None = None,
    description: str | None = None,
    setup_script: str | None = None,
    post_execution_script: str | None = None,
    metadata: dict[str, Any] | None = None,
    sandbox_id: str | None = None,
    depends_on: list[str | Step] | None = None,
) -> Step | Callable[[StepFunction[...]], Step]:
    """Decorator for configuring a Step with execution metadata."""

    def _create_step(the_func: StepFunction[...]) -> Step:
        schema = function_schema(func=the_func)
        # Get the absolute file path of the function
        func_file = inspect.getfile(the_func)
        # Use get_relative_path which finds repo root by looking for .git or pyproject.toml
        file_path = get_relative_path(func_file)

        # Get the line number where the function is defined
        try:
            line_number = inspect.getsourcelines(the_func)[1]
        except (OSError, TypeError):
            # Fallback if source is not available (e.g., built-in functions, C extensions)
            line_number = None

        data = step_data(
            function_schema=schema,
            name=name,
            description=description,
            setup_script=setup_script,
            post_execution_script=post_execution_script,
            metadata=metadata,
            sandbox_id=sandbox_id,
            depends_on=depends_on,
            file_path=file_path,
            line_number=line_number,
        )

        async def _on_invoke_step_impl(input: str, step_results: str) -> str:
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

            # If a cached result exists, use it
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

            args, kwargs_dict = schema.to_call_args(parsed)

            logger.debug(f"Step call args: {args}, kwargs: {kwargs_dict}")

            if inspect.iscoroutinefunction(the_func):
                result = await the_func(*args, **kwargs_dict)
            else:
                result = the_func(*args, **kwargs_dict)

            logger.debug(f"Step {data.name} completed.")

            # Serialize the result to JSON
            try:
                return schema.serialize_return_value(result)
            except (ValueError, TypeError) as e:
                raise StepError(
                    f"Failed to serialize return value for step {schema.name}: {e}"
                ) from e

        step = Step(
            step_data=data,
            on_invoke_step=_on_invoke_step_impl,
            _original_func=the_func,
        )

        STEP_REGISTRY[data.name] = step

        return step

    # If func is actually a callable, we were used as @step with no parentheses
    if callable(func):
        return _create_step(func)

    # Otherwise, we were used as @step(...), so return a decorator
    def decorator(real_func: StepFunction[...]) -> StepFunction[...]:
        return _create_step(real_func)

    return decorator


def get_dsl_output() -> Dict[str, Any]:
    """Generate DSL output from the step registry with type information."""
    dsl_output = {}
    for step_name, step in STEP_REGISTRY.items():
        # STEP_REGISTRY stores Step objects
        step_dict = step.step_data.model_dump(exclude_none=True)
        dsl_output[step_name] = step_dict

    return dsl_output
