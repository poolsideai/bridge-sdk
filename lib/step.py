from typing import (
    Annotated,
    Any,
    Callable,
    Optional,
    Dict,
    get_args,
    get_origin,
    get_type_hints,
    overload,
)
from pydantic.fields import FieldInfo
from typing_extensions import ParamSpec
from pydantic import BaseModel, Field, create_model
import inspect

from lib.utils import get_relative_path

StepParams = ParamSpec("StepParams")
StepFunction = Callable[StepParams, Any]

STEP_INPUT_ANNOTATION_KEY = "from_step_result"


class StepData(BaseModel):
    name: str
    """The name of the step."""
    description: str | None = None
    """The description of the step."""
    setup_script: str | None = None
    """The script to run before the step execution."""
    post_execution_script: str | None = None
    """The script to run after the step execution."""
    metadata: dict[str, Any] | None = None
    """Arbitrary metadata for the step."""
    sandbox_id: str | None = None
    """ID of the sandbox the step will be executed in. If not provided, a default sandbox will be used."""
    depends_on_steps: list[str] = Field(default_factory=list)
    """The steps that this step depends on. Either a step name if defined in the same reposiory, or a step ID."""
    file_path: str
    """The file path of the step function."""
    line_number: int
    """The line number of the step function."""
    params_json_schema: dict[str, Any]
    """The JSON schema for the function's parameters, derived from the Pydantic model."""
    return_json_schema: dict[str, Any]
    """The JSON schema for the function's return value, derived from the Pydantic model."""
    params_from_step_results: dict[str, str] = Field(default_factory=dict)
    """A dictionary of param name to step name or ID, defining which steps results can be used to populate the param."""


def get_step_data(
    func: StepFunction[...],
    name_override: str | None = None,
    description: str | None = None,
    setup_script: str | None = None,
    post_execution_script: str | None = None,
    metadata: dict[str, Any] | None = None,
    sandbox_id: str | None = None,
    depends_on_steps: list[str] | None = None,
    params_from_step_results: dict[str, str] | None = None,
) -> StepData:
    """Create a StepData object from a step function."""

    try:
        abs_file_path = inspect.getfile(func)
        # Get the line number where the function definition starts
        _, line_number = inspect.getsourcelines(func)
        # Convert to relative path from repo root
        file_path = get_relative_path(abs_file_path)
    except (OSError, TypeError):
        # Fallback if inspect fails (e.g., for built-in functions or in some edge cases)
        file_path = None
        line_number = None

    type_hints_with_extras = get_type_hints(func, include_extras=True)
    type_hints: dict[str, Any] = {}

    for name, annotation in type_hints_with_extras.items():
        stripped_ann, annotation_metadata = _strip_annotated(annotation)
        type_hints[name] = stripped_ann

    # Name override takes precedence over function name
    func_name = name_override or func.__name__

    sig = inspect.signature(func)
    params = list(sig.parameters.items())

    fields: dict[str, Any] = {}

    for name, param in params:
        ann = type_hints.get(name, param.annotation)
        default = param.default

        # If there's no type hint, assume `Any`
        if ann == inspect._empty:
            ann = Any

        # Handle different parameter kinds
        if param.kind == param.VAR_POSITIONAL:
            # e.g. *args: extend positional args
            if get_origin(ann) is tuple:
                # e.g. def foo(*args: tuple[int, ...]) -> treat as List[int]
                args_of_tuple = get_args(ann)
                if len(args_of_tuple) == 2 and args_of_tuple[1] is Ellipsis:
                    ann = list[args_of_tuple[0]]  # type: ignore
                else:
                    ann = list[Any]
            else:
                # If user wrote *args: int, treat as List[int]
                ann = list[ann]  # type: ignore

            # Default factory to empty list
            fields[name] = (
                ann,
                Field(default_factory=list),
            )

        elif param.kind == param.VAR_KEYWORD:
            # **kwargs handling
            if get_origin(ann) is dict:
                # e.g. def foo(**kwargs: dict[str, int])
                dict_args = get_args(ann)
                if len(dict_args) == 2:
                    ann = dict[dict_args[0], dict_args[1]]  # type: ignore
                else:
                    ann = dict[str, Any]
            else:
                # e.g. def foo(**kwargs: int) -> Dict[str, int]
                ann = dict[str, ann]  # type: ignore

            fields[name] = (
                ann,
                Field(default_factory=dict),
            )

        else:
            # Normal parameter
            if default == inspect._empty:
                # Required field
                fields[name] = (
                    ann,
                    Field(...),
                )
            elif isinstance(default, FieldInfo):
                # Parameter with a default value that is a Field(...)
                fields[name] = (
                    ann,
                    FieldInfo.merge_field_infos(default, default.description),
                )
            else:
                # Parameter with a default value
                fields[name] = (
                    ann,
                    Field(default=default),
                )

    # 3. Dynamically build a Pydantic model
    dynamic_model = create_model(f"{func_name}_args", __base__=BaseModel, **fields)

    # 4. Build JSON schema from that model
    json_schema = dynamic_model.model_json_schema()

    # 5. Build return type JSON schema
    return_type = type_hints.get("return", Any)
    if return_type == inspect.Signature.empty:
        return_type = Any

    try:
        dynamic_return_model = create_model(
            f"{func_name}_return",
            __base__=BaseModel,
            return_type=(return_type, Field(...)),
        )
        full_return_schema = dynamic_return_model.model_json_schema()
        # Extract just the "return_type" field schema from the properties
        if (
            "properties" in full_return_schema
            and "return_type" in full_return_schema["properties"]
        ):
            return_json_schema = full_return_schema["properties"]["return_type"]
            # Preserve $defs if they exist, as they may be needed for $ref references
            if "$defs" in full_return_schema:
                return_json_schema = {
                    **return_json_schema,
                    "$defs": full_return_schema["$defs"],
                }
        else:
            return_json_schema = full_return_schema
    except Exception:
        return_json_schema = {}

    return StepData(
        name=func_name,
        description=description,
        setup_script=setup_script,
        post_execution_script=post_execution_script,
        metadata=metadata,
        sandbox_id=sandbox_id,
        depends_on_steps=depends_on_steps or [],
        params_json_schema=json_schema,
        return_json_schema=return_json_schema,
        file_path=file_path,
        line_number=line_number,
        params_from_step_results=params_from_step_results or {},
    )


def _strip_annotated(annotation: Any) -> tuple[Any, tuple[Any, ...]]:
    """Returns the underlying annotation and any metadata from typing.Annotated."""

    metadata: tuple[Any, ...] = ()
    ann = annotation

    while get_origin(ann) is Annotated:
        args = get_args(ann)
        if not args:
            break
        ann = args[0]
        metadata = (*metadata, *args[1:])

    return ann, metadata


STEP_REGISTRY: Dict[str, StepData] = {}


@overload
def step(
    func: StepFunction[...],
    *,
    name_override: str | None = None,
    description: str | None = None,
    setup_script: str | None = None,
    post_execution_script: str | None = None,
    metadata: dict[str, Any] | None = None,
    sandbox_id: str | None = None,
    depends_on_steps: list[str] | None = None,
    params_from_step_results: dict[str, str] | None = None,
) -> StepData:
    """Overload for usage as @step (no parentheses)."""
    ...


@overload
def step(
    *,
    name_override: str | None = None,
    description: str | None = None,
    setup_script: str | None = None,
    post_execution_script: str | None = None,
    metadata: dict[str, Any] | None = None,
    sandbox_id: str | None = None,
    depends_on_steps: list[str] | None = None,
    params_from_step_results: dict[str, str] | None = None,
) -> Callable[[StepFunction[...]], StepData]:
    """Overload for usage as @step(...)"""
    ...


def step(
    func: StepFunction[...] | None = None,
    *,
    name_override: str | None = None,
    description: str | None = None,
    setup_script: str | None = None,
    post_execution_script: str | None = None,
    metadata: dict[str, Any] | None = None,
    sandbox_id: str | None = None,
    depends_on_steps: list[str] | None = None,
    params_from_step_results: dict[str, str] | None = None,
) -> StepData | Callable[[StepFunction[...]], StepData]:
    """Decorator for configuring a Step with execution metadata."""

    def _get_step_data(the_func: StepFunction[...]) -> StepData:
        step_data = get_step_data(
            the_func,
            name_override=name_override,
            description=description,
            setup_script=setup_script,
            post_execution_script=post_execution_script,
            metadata=metadata,
            sandbox_id=sandbox_id,
            depends_on_steps=depends_on_steps,
            params_from_step_results=params_from_step_results,
        )

        STEP_REGISTRY[step_data.name] = step_data

        def wrapper(*args, **kwargs):
            return the_func(*args, **kwargs)

        return wrapper

    # If func is actually a callable, we were used as @function_tool with no parentheses
    if callable(func):
        return _get_step_data(func)

    # Otherwise, we were used as @function_tool(...), so return a decorator
    def decorator(real_func: StepFunction[...]) -> StepData:
        return _get_step_data(real_func)

    return decorator


# Annotation helpers
def step_result(step_name: str) -> str:
    return f"step:{step_name}"


def extract_step_result_annotation(annotation: str) -> Optional[str]:
    if annotation.startswith("step:"):
        # Use removeprefix (Python 3.9+) or slice manually
        return annotation[5:].strip()  # Remove "step:" prefix (5 characters)
    else:
        return None


def get_dsl_output() -> Dict[str, Any]:
    """Generate DSL output from the step registry with type information."""
    dsl_output = {}
    for step_name, step_data in STEP_REGISTRY.items():
        # STEP_REGISTRY stores StepData directly
        step_dict = step_data.model_dump(exclude_none=True)
        dsl_output[step_name] = step_dict

    return dsl_output


if __name__ == "__main__":
    # Import examples which will populate lib.step.STEP_REGISTRY via 'from lib import step'
    import examples.example  # noqa: F401
    import json

    # Import get_dsl_output from lib package to use the same STEP_REGISTRY that was populated
    # by the decorators in examples.example (which imported from lib.step)
    from lib import get_dsl_output

    print(json.dumps(get_dsl_output(), indent=2))
