from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from lib.step import StepFunction

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