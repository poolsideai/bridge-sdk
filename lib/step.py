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
    file_path: str | None = None
    """The file path of the step function."""
    line_number: int | None = None
    """The line number of the step function."""
    params_json_schema: dict[str, Any]
    """The JSON schema for the function's parameters, derived from the Pydantic model."""
    return_json_schema: dict[str, Any]
    """The JSON schema for the function's return value, derived from the Pydantic model."""
    params_from_step_results: dict[str, str] = Field(default_factory=dict)
    """A dictionary of param name to step name or ID, defining which steps results can be used to populate the param."""


def get_step_data(
    func: StepFunction[...],
    name: str | None = None,
    description: str | None = None,
    setup_script: str | None = None,
    post_execution_script: str | None = None,
    metadata: dict[str, Any] | None = None,
    sandbox_id: str | None = None,
    depends_on: list[str] | None = None,
) -> StepData:
    """Create a StepData object from a step function."""

    params_from_step_results_dict: dict[str, str] = {}

    # Get the absolute file path of the function
    func_file = inspect.getfile(func)
    # Use get_relative_path which finds repo root by looking for .git or pyproject.toml
    file_path = get_relative_path(func_file)

    # Get the line number where the function is defined
    try:
        line_number = inspect.getsourcelines(func)[1]
    except (OSError, TypeError):
        # Fallback if source is not available (e.g., built-in functions, C extensions)
        line_number = None

    type_hints_with_extras = get_type_hints(func, include_extras=True)
    type_hints: dict[str, Any] = {}

    for param_name, annotation in type_hints_with_extras.items():
        stripped_ann, annotation_metadata = _strip_annotated(annotation)
        type_hints[param_name] = stripped_ann
        from_step_result = extract_step_result_annotation(annotation_metadata)
        if from_step_result:
            params_from_step_results_dict[param_name] = from_step_result

    # Name override takes precedence over function name
    func_name = name or func.__name__

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
        depends_on_steps=depends_on or [],
        params_json_schema=json_schema,
        return_json_schema=return_json_schema,
        file_path=file_path,
        line_number=line_number,
        params_from_step_results=params_from_step_results_dict,
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


class StepRecord:
    """A record containing both the step function and its metadata."""

    def __init__(self, func: StepFunction[...], data: StepData):
        self.func = func
        self.data = data


STEP_REGISTRY: Dict[str, StepRecord] = {}


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
    depends_on: list[str] | None = None,
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
    depends_on: list[str] | None = None,
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
    depends_on: list[str] | None = None,
) -> StepFunction[...] | Callable[[StepFunction[...]], StepFunction[...]]:
    """Decorator for configuring a Step with execution metadata."""

    def _get_step_data(the_func: StepFunction[...]) -> StepFunction[...]:
        step_data = get_step_data(
            the_func,
            name=name,
            description=description,
            setup_script=setup_script,
            post_execution_script=post_execution_script,
            metadata=metadata,
            sandbox_id=sandbox_id,
            depends_on=depends_on,
        )

        STEP_REGISTRY[step_data.name] = StepRecord(func=the_func, data=step_data)

        def wrapper(*args, **kwargs):
            return the_func(*args, **kwargs)

        return wrapper

    # If func is actually a callable, we were used as @step with no parentheses
    if callable(func):
        return _get_step_data(func)

    # Otherwise, we were used as @step(...), so return a decorator
    def decorator(real_func: StepFunction[...]) -> StepFunction[...]:
        return _get_step_data(real_func)

    return decorator


# Annotation helpers
def step_result(step_name: str) -> str:
    return f"step:{step_name}"


def extract_step_result_annotation(annotations: tuple[Any, ...]) -> Optional[str]:
    for annotation in annotations:
        if isinstance(annotation, str) and annotation.startswith("step:"):
            return annotation[5:].strip()  # Remove "step:" prefix (5 characters)
    return None


def get_dsl_output() -> Dict[str, Any]:
    """Generate DSL output from the step registry with type information."""
    dsl_output = {}
    for step_name, step_record in STEP_REGISTRY.items():
        # STEP_REGISTRY stores StepRecord objects
        step_dict = step_record.data.model_dump(exclude_none=True)
        dsl_output[step_name] = step_dict

    return dsl_output
