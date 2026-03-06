# Copyright 2026 Poolside, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""EvalData model and factory for extracting eval metadata from functions."""

from __future__ import annotations

import inspect
from typing import Any, Callable, Optional, get_args, get_origin, get_type_hints

from pydantic import BaseModel, TypeAdapter

from bridge_sdk.eval_types import PipelineEvalContext, StepEvalContext, EvalResult
from bridge_sdk.utils import get_relative_path


class EvalData(BaseModel):
    """Serializable eval metadata for DSL output."""

    name: str
    """The name of the eval function."""

    rid: Optional[str] = None
    """Optional stable resource identifier (UUID)."""

    description: Optional[str] = None
    """Optional human-readable description."""

    context_type: str
    """Whether this eval targets a 'step' or 'pipeline'."""

    file_path: Optional[str] = None
    """The file path of the eval function."""

    file_line_number: Optional[int] = None
    """The line number of the eval function."""

    metrics_schema: dict[str, Any]
    """JSON Schema of the metrics TypedDict used in EvalResult[M]."""

    input_type_schema: Optional[dict[str, Any]] = None
    """JSON Schema of the input type parameter, or null if Any."""

    output_type_schema: Optional[dict[str, Any]] = None
    """JSON Schema of the output type parameter, or null if Any."""


def _is_subclass_safe(tp: Any, target: type) -> bool:
    """Check if tp is a subclass of target, returning False instead of raising."""
    try:
        return tp is not None and issubclass(tp, target)
    except TypeError:
        return False


def _is_any(tp: Any) -> bool:
    """Check if a type is Any."""
    return tp is Any


def _type_schema_or_none(tp: Any) -> dict[str, Any] | None:
    """Generate a JSON schema for a type, returning None if it's Any."""
    if _is_any(tp):
        return None
    try:
        return TypeAdapter(tp).json_schema()
    except Exception:
        return None


def _extract_eval_type_info(
    func: Callable[..., Any],
) -> tuple[str, dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    """Extract context_type, metrics_schema, and I/O type schemas from an eval function.

    Returns:
        (context_type, metrics_schema, input_type_schema, output_type_schema)
    """
    hints = get_type_hints(func, include_extras=True)

    # Find the first parameter's type hint (the context)
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())
    if not params:
        raise TypeError(
            f"Eval function '{func.__name__}' must accept at least one parameter "
            f"(StepEvalContext or PipelineEvalContext)"
        )

    ctx_hint = hints.get(params[0])
    if ctx_hint is None:
        raise TypeError(
            f"Eval function '{func.__name__}' must have a type annotation on its "
            f"first parameter (StepEvalContext[I, O] or PipelineEvalContext[I, O])"
        )

    # Determine context_type from the origin of the generic
    origin = get_origin(ctx_hint)
    if _is_subclass_safe(origin, StepEvalContext) or _is_subclass_safe(ctx_hint, StepEvalContext):
        context_type = "step"
    elif _is_subclass_safe(origin, PipelineEvalContext) or _is_subclass_safe(ctx_hint, PipelineEvalContext):
        context_type = "pipeline"
    else:
        raise TypeError(
            f"Eval function '{func.__name__}' first parameter must be typed as "
            f"StepEvalContext[I, O] or PipelineEvalContext[I, O], "
            f"got {ctx_hint!r}"
        )

    # Extract I, O from the generic parameters
    ctx_args = get_args(ctx_hint)
    if ctx_args and len(ctx_args) >= 2:
        input_type, output_type = ctx_args[0], ctx_args[1]
    else:
        input_type, output_type = Any, Any

    input_type_schema = _type_schema_or_none(input_type)
    output_type_schema = _type_schema_or_none(output_type)

    # Extract metrics schema from return type EvalResult[M]
    return_hint = hints.get("return")
    metrics_schema: dict[str, Any] = {}

    if return_hint is not None:
        ret_origin = get_origin(return_hint)
        if _is_subclass_safe(ret_origin, EvalResult) or _is_subclass_safe(return_hint, EvalResult):
            ret_args = get_args(return_hint)
            if ret_args:
                metrics_type = ret_args[0]
                if not _is_any(metrics_type):
                    try:
                        metrics_schema = TypeAdapter(metrics_type).json_schema()
                    except Exception:
                        pass

    return context_type, metrics_schema, input_type_schema, output_type_schema


def create_eval_data(
    func: Callable[..., Any],
    *,
    name: str | None = None,
    rid: str | None = None,
    description: str | None = None,
) -> EvalData:
    """Create an EvalData object from an eval function.

    Extracts context_type, metrics_schema, and I/O type schemas from
    the function's type hints.
    """
    context_type, metrics_schema, input_type_schema, output_type_schema = (
        _extract_eval_type_info(func)
    )

    func_file = inspect.getfile(func)
    file_path = get_relative_path(func_file)

    try:
        line_number = inspect.getsourcelines(func)[1]
    except (OSError, TypeError):
        line_number = None

    return EvalData(
        name=name or func.__name__,
        rid=rid,
        description=description,
        context_type=context_type,
        file_path=file_path,
        file_line_number=line_number,
        metrics_schema=metrics_schema,
        input_type_schema=input_type_schema,
        output_type_schema=output_type_schema,
    )
