import inspect
from typing import Any, Callable, Optional

from pydantic import BaseModel, Field

from bridge_sdk.annotations import extract_step_result_annotation
from bridge_sdk.function_schema import FunctionSchema
from bridge_sdk.utils import get_relative_path


class StepData(BaseModel):
    name: str
    """The name of the step."""
    description: str | None
    """The description of the step."""
    setup_script: str | None = None
    """The script to run before the step execution."""
    post_execution_script: str | None = None
    """The script to run after the step execution."""
    metadata: dict[str, Any] | None = None
    """Arbitrary metadata for the step."""
    execution_environment_id: str | None = None
    """ID of the execution environment that the step will be executed in. If not provided, a default sandbox will be used."""
    depends_on: list[str] = Field(default_factory=list)
    """The steps that this step depends on. Either a step name if defined in the same repository, or a step ID."""
    file_path: str | None = None
    """The file path of the step function."""
    file_line_number: int | None = None
    """The line number of the step function."""
    params_json_schema: dict[str, Any]
    """The json schema of the params."""
    return_json_schema: dict[str, Any]
    """The return schema of the function."""
    params_from_step_results: dict[str, str] = Field(default_factory=dict)
    """A dictionary of param name to step name, defining which steps results can be used to populate the param."""
    credential_bindings: dict[str, str] | None = None
    """A dictionary of credential name to credential ID, defining which credentials can be used to populate the step."""


def create_step_data(
    func: Callable[..., Any],
    function_schema: FunctionSchema,
    name: str | None = None,
    description: str | None = None,
    setup_script: str | None = None,
    post_execution_script: str | None = None,
    metadata: dict[str, Any] | None = None,
    sandbox_id: str | None = None,
    credential_bindings: dict[str, str] | None = None,
) -> StepData:
    """Create a StepData object from a step function."""
    # Extract file path and line number from the function
    func_file = inspect.getfile(func)
    file_path = get_relative_path(func_file)

    try:
        line_number = inspect.getsourcelines(func)[1]
    except (OSError, TypeError):
        # Fallback if source is not available (e.g., built-in functions, C extensions)
        line_number = None

    params_from_step_results_dict: dict[str, str] = {}

    for param, annotations in function_schema.param_annotations.items():
        from_step = extract_step_result_annotation(annotations)
        if from_step:
            params_from_step_results_dict[param] = from_step

    resolved_depends_on = set(params_from_step_results_dict.values())

    return StepData(
        name=name or function_schema.name,
        description=description,
        setup_script=setup_script,
        post_execution_script=post_execution_script,
        metadata=metadata,
        execution_environment_id=sandbox_id,
        depends_on=list(resolved_depends_on),
        params_json_schema=function_schema.params_json_schema,
        return_json_schema=function_schema.return_json_schema,
        file_path=file_path,
        file_line_number=line_number,
        params_from_step_results=params_from_step_results_dict,
        credential_bindings=credential_bindings,
    )
