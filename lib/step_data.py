from typing import Any, Callable, Optional, TYPE_CHECKING, Union
from pydantic import BaseModel, Field

from lib.function_schema import FunctionSchema

if TYPE_CHECKING:
    from lib.step import Step


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
    sandbox_id: str | None = None
    """ID of the sandbox the step will be executed in. If not provided, a default sandbox will be used."""
    depends_on: list[str] = Field(default_factory=list)
    """The steps that this step depends on. Either a step name if defined in the same reposiory, or a step ID."""
    file_path: str | None = None
    """The file path of the step function."""
    line_number: int | None = None
    """The line number of the step function."""
    params_from_step_results: dict[str, str] = Field(default_factory=dict)
    """A dictionary of param name to step name or ID, defining which steps results can be used to populate the param."""
    params_json_schema: dict[str, Any]
    """The json schema of the params."""
    return_json_schema: dict[str, Any]
    """The return schema of the params."""


def step_data(
    function_schema: FunctionSchema,
    name: str | None = None,
    description: str | None = None,
    setup_script: str | None = None,
    post_execution_script: str | None = None,
    metadata: dict[str, Any] | None = None,
    sandbox_id: str | None = None,
    depends_on: list[Union[str, "Step"]] | None = None,
    file_path: str | None = None,
    line_number: int | None = None,
) -> StepData:
    """Create a StepData object from a step function."""
    params_from_step_results_dict: dict[str, str] = {}

    for param, annotations in function_schema.param_annotations.items():
        from_step = extract_step_result_annotation(annotations)
        if from_step:
            params_from_step_results_dict[param] = from_step

    # Convert Step objects to their names, keep strings as-is
    resolved_depends_on: list[str] = []
    for depends in depends_on or []:
        # Check if it's a Step object by checking for step_data attribute
        # This avoids circular import issues
        if hasattr(depends, "step_data") and hasattr(depends, "on_invoke_step"):
            resolved_depends_on.append(depends.step_data.name)
        else:
            resolved_depends_on.append(depends)

    return StepData(
        name=name or function_schema.name,
        description=description,
        setup_script=setup_script,
        post_execution_script=post_execution_script,
        metadata=metadata,
        sandbox_id=sandbox_id,
        depends_on=resolved_depends_on,
        params_json_schema=function_schema.params_json_schema,
        return_json_schema=function_schema.return_json_schema,
        file_path=file_path,
        line_number=line_number,
        params_from_step_results=params_from_step_results_dict,
    )


# Annotation helpers
STEP_RESULT_ANNOTATION_PREFIX = "step"


def step_result(step: Union[str, "Step"]) -> str:
    """Create a step_result annotation.

    Args:
        step: Either a step name (str) or a Step object. If a Step object is provided,
              the step's actual name will be used (which is the function name if no
              override was provided, or the override name if @step(name=...) was used).

    Returns:
        A string annotation in the format "step:step_name"
    """
    # Check if it's a Step object by checking for step_data attribute
    # This avoids circular import issues
    if hasattr(step, "step_data") and hasattr(step, "on_invoke_step"):
        # Use the step's actual name (could be function name or override name)
        step_name = step.step_data.name
    else:
        # It's a string, use it directly
        step_name = step

    return f"{STEP_RESULT_ANNOTATION_PREFIX}:{step_name}"


def extract_step_result_annotation(annotations: tuple[Any, ...]) -> Optional[str]:
    for annotation in annotations:
        if isinstance(annotation, str) and annotation.startswith(
            f"{STEP_RESULT_ANNOTATION_PREFIX}:"
        ):
            return annotation[5:].strip()  # Remove "step:" prefix (5 characters)
    return None
