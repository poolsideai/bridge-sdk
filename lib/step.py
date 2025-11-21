from typing import Any, Optional, Dict, get_args
from pydantic import BaseModel
import inspect
from pathlib import Path


class ParamInfo(BaseModel):
    """Information about a step function parameter."""

    name: str
    is_step_input: bool = False
    is_step_result: bool = False
    step_result_name: str | None = None
    actual_type: Any = None


class StepData(BaseModel):
    name: str | None = None
    setup_script: str | None = None
    post_execution_script: str | None = None
    metadata: dict[str, Any] | None = None
    execution_env: dict[str, Any] | None = None
    depends_on: list[str] | None = None
    file_path: str | None = None
    line_number: int | None = None
    parameters: list[ParamInfo] | None = None


class StepRecord:
    def __init__(self, func, data: StepData):
        self.func = func
        self.data = data


STEP_REGISTRY: Dict[str, StepRecord] = {}


def _find_repo_root(file_path: str) -> Optional[Path]:
    """Find the repository root by looking for .git directory or pyproject.toml."""
    path = Path(file_path).resolve()

    # If it's a file, start from its parent directory
    if path.is_file():
        path = path.parent

    # Walk up the directory tree looking for repo markers
    for parent in [path] + list(path.parents):
        # Check for common repository markers
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            return parent

    # If no marker found, return None
    return None


def _get_relative_path(file_path: str) -> Optional[str]:
    """Convert an absolute file path to a relative path from the repository root."""
    if not file_path:
        return None

    try:
        abs_path = Path(file_path).resolve()
        repo_root = _find_repo_root(file_path)

        if repo_root:
            try:
                relative_path = abs_path.relative_to(repo_root)
                return str(relative_path)
            except ValueError:
                # File is not under the repo root
                return file_path
        else:
            # No repo root found, return absolute path as fallback
            return file_path
    except Exception:
        # If anything goes wrong, return the original path
        return file_path


def _extract_parameter_info(func) -> list[ParamInfo]:
    """Extract parameter information from a function signature."""
    sig = inspect.signature(func)
    param_infos = []

    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue

        param_info = ParamInfo(name=param_name)

        # Check if it's an Annotated type
        if (
            param.annotation != inspect.Parameter.empty
            and hasattr(param.annotation, "__metadata__")
            and (metadata := param.annotation.__metadata__)
        ):
            annotation_value = metadata[0]

            # Check if it's a step input
            if annotation_value == STEP_INPUT:
                param_info.is_step_input = True
                if type_args := get_args(param.annotation):
                    actual_type = type_args[0]
                    # Convert type(None) to None for consistency
                    param_info.actual_type = (
                        None if actual_type is type(None) else actual_type
                    )
                else:
                    param_info.actual_type = None

            # Check if it's a step result
            elif step_result_name := extract_step_result_annotation(annotation_value):
                param_info.is_step_result = True
                param_info.step_result_name = step_result_name
                if type_args := get_args(param.annotation):
                    actual_type = type_args[0]
                    # Convert type(None) to None for consistency
                    param_info.actual_type = (
                        None if actual_type is type(None) else actual_type
                    )
                else:
                    param_info.actual_type = None

        param_infos.append(param_info)

    return param_infos


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
        # Get file path and line number where the function is defined
        try:
            abs_file_path = inspect.getfile(func)
            # Get the line number where the function definition starts
            _, line_number = inspect.getsourcelines(func)
            # Convert to relative path from repo root
            file_path = _get_relative_path(abs_file_path)
        except (OSError, TypeError):
            # Fallback if inspect fails (e.g., for built-in functions or in some edge cases)
            file_path = None
            line_number = None

        # Extract parameter information from function signature
        parameters = _extract_parameter_info(func)

        step_data = StepData(
            name=name,
            setup_script=setup_script,
            post_execution_script=post_execution_script,
            metadata=metadata,
            execution_env=execution_env,
            depends_on=depends_on or [],
            file_path=file_path,
            line_number=line_number,
            parameters=parameters,
        )
        step_record = StepRecord(func=func, data=step_data)
        STEP_REGISTRY[name] = step_record

        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

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


STEP_INPUT = "input"
