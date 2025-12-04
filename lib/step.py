import inspect
import json
from functools import update_wrapper
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    overload,
)
from pydantic import TypeAdapter, ValidationError
from typing_extensions import ParamSpec, TypeVar

from lib.exceptions import StepError
from lib.function_schema import FunctionSchema, create_function_schema
from lib.logger import logger
from lib.step_data import StepData, create_step_data

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

    async def on_invoke_step(self, input_json: str, step_results: str) -> str:
        """Invoke the step with JSON input and return JSON output.

        Args:
            input_json: JSON string of input parameters.
            step_results: JSON string of results from previous steps.

        Returns:
            JSON string of the function's return value.
        """
        try:
            input_data: dict[str, Any] = json.loads(input_json) if input_json else {}
        except Exception as e:
            raise StepError(
                f"Invalid JSON input for step {self._schema.name}: {input_json}"
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
                str if self._schema.return_type in (Any, None) else self._schema.return_type
            )
            return TypeAdapter(return_type).dump_json(result).decode()
        except (ValueError, TypeError) as e:
            raise StepError(
                f"Failed to serialize return value for step {self.step_data.name}: {e}"
            ) from e


STEP_REGISTRY: Dict[str, StepFunction[..., Any]] = {}

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
) -> StepFunction[P, R]:
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
) -> Callable[[Callable[P, R]], StepFunction[P, R]]:
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
) -> StepFunction[P, R] | Callable[[Callable[P, R]], StepFunction[P, R]]:
    """Decorator for configuring a Step with execution metadata.

    Returns a StepFunction wrapper with step_data and on_invoke_step attributes.
    """

    def _create_step_function(the_func: Callable[P, R]) -> StepFunction[P, R]:
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

        step_function = StepFunction(the_func, schema, data)
        STEP_REGISTRY[data.name] = step_function
        return step_function

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