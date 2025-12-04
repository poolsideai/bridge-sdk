from typing import Callable, Any, Optional

STEP_RESULT_PREFIX = "step:"
def step_result(step: str | Callable[..., Any]) -> str:
    """Create a step_result annotation.

    Args:
        step: Either a step name (str) or a @step-decorated function. If a decorated
              function is provided, the step's actual name will be used (which is the
              function name if no override was provided, or the override name if
              @step(name=...) was used).

    Returns:
        A string annotation in the format "step:step_name"
    """
    # Check if it's a @step-decorated function by checking for step_data attribute
    if hasattr(step, "step_data") and hasattr(step, "on_invoke_step"):
        # Use the step's actual name (could be function name or override name)
        step_name = step.step_data.name  # type: ignore[union-attr]
    else:
        # It's a string, use it directly
        step_name = step  # type: ignore[assignment]

    return f"{STEP_RESULT_PREFIX}{step_name}"


def extract_step_result_annotation(annotations: tuple[Any, ...]) -> Optional[str]:
    for annotation in annotations:
        if isinstance(annotation, str) and annotation.startswith(STEP_RESULT_PREFIX):
            return annotation[len(STEP_RESULT_PREFIX):].strip()
    return None