import inspect
import os
import sys
from typing import Any, Callable, Generic, TypeVar, Optional, Dict, Type, Coroutine
from pydantic import BaseModel

# This is the path to "main.py"/entrypoint, if entrypoint changes, may need to update this logic
REPO_ROOT = os.path.dirname(os.path.abspath(sys.argv[0]))

class StepData(BaseModel):
    name: str | None = None
    setup_script: str | None = None,
    post_execution_script: str | None = None,
    metadata: dict[str, Any] | None = None,
    execution_env: dict[str, Any] | None = None,
    depends_on: list[str] | None = None,
    file_name: str
    file_line_number: int

class StepRecord:
    def __init__(self, func, data: StepData):
        self.func = func
        self.data = data

STEP_REGISTRY: Dict[str,  StepRecord] = {}
def step(
    name: str | None = None,
    setup_script: str | None = None,
    post_execution_script: str | None = None,
    metadata: dict[str, Any] | None = None,
    execution_env: dict[str, Any] | None = None,
    depends_on: list[str] | None = None,
):
    """Decorator for configuring a Step with execution metadata."""
    def decorator(func):
        _, line_number = inspect.getsourcelines(func)
        step_data = StepData(
            name=name,
            setup_script=setup_script,
            post_execution_script=post_execution_script,
            metadata=metadata,
            execution_env=execution_env,
            depends_on=depends_on or [],
            file_name=os.path.relpath(inspect.getfile(func), REPO_ROOT),
            file_line_number=line_number
        )
        step_record = StepRecord(func=func, data=step_data)
        STEP_REGISTRY[name] = step_record
        def wrapper(*args, **kwargs):
            func(*args, **kwargs)
        return wrapper
    return decorator

# Annotation helpers
def step_result(step_name: str) -> str:
    return f"step:{step_name}"

def extract_step_result_annotation(annotation: str) -> Optional[str]:
    if annotation.startswith("step:"):
        return annotation.lstrip("step:").strip()  # Remove "step:" prefix
    else:
        return None

STEP_INPUT = "input"