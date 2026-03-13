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

"""EvalFunction class and eval registry."""

from __future__ import annotations

import inspect
import json
from functools import update_wrapper
from typing import Any, Callable, Dict, TypeVar, get_args, get_type_hints

from pydantic import TypeAdapter

from bridge_sdk.eval_data import EvalData, create_eval_data
from bridge_sdk.eval_types import (
    EvalResult,
    PipelineEvalContext,
    StepEvalContext,
)

EVAL_REGISTRY: Dict[str, "EvalFunction"] = {}

def _get_context_io_types(func: Callable[..., Any]) -> tuple[Any, Any]:
    """Extract I/O generic types from eval context annotation."""
    hints = get_type_hints(func, include_extras=True)
    params = list(inspect.signature(func).parameters.keys())
    if not params:
        return Any, Any

    ctx_hint = hints.get(params[0])
    if ctx_hint is None:
        return Any, Any

    ctx_args = get_args(ctx_hint)
    if not ctx_args:
        meta = getattr(ctx_hint, "__pydantic_generic_metadata__", None)
        if meta:
            ctx_args = tuple(meta.get("args", ()))

    if len(ctx_args) >= 2:
        input_type = Any if isinstance(ctx_args[0], TypeVar) else ctx_args[0]
        output_type = Any if isinstance(ctx_args[1], TypeVar) else ctx_args[1]
        return input_type, output_type
    return Any, Any


def _build_step_eval_context(
    data: dict[str, Any],
    input_type: Any = Any,
    output_type: Any = Any,
) -> StepEvalContext[Any, Any]:
    """Build a StepEvalContext from a deserialized JSON dict using pydantic validation."""
    payload = dict(data)
    payload.setdefault("step_input", None)
    payload.setdefault("step_output", None)
    model_type = StepEvalContext[input_type, output_type]
    try:
        return TypeAdapter(model_type).validate_python(payload)
    except Exception as e:
        raise TypeError(f"Failed to parse step eval context: {e}") from e


def _build_pipeline_eval_context(
    data: dict[str, Any],
    input_type: Any = Any,
    output_type: Any = Any,
) -> PipelineEvalContext[Any, Any]:
    """Build a PipelineEvalContext from a deserialized JSON dict using pydantic validation."""
    payload = dict(data)
    payload.setdefault("pipeline_input", None)
    payload.setdefault("pipeline_output", None)
    model_type = PipelineEvalContext[input_type, output_type]
    try:
        return TypeAdapter(model_type).validate_python(payload)
    except Exception as e:
        raise TypeError(f"Failed to parse pipeline eval context: {e}") from e


def _encode_eval_result_value(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"type": "boolean", "boolean_value": value}
    if isinstance(value, (int, float)):
        return {"type": "number", "number_value": float(value)}
    if isinstance(value, str):
        return {"type": "string", "string_value": value}
    raise TypeError(
        "EvalResult.result must be bool, number, or string, "
        f"got {type(value).__name__}"
    )


def _serialize_eval_result(result: EvalResult[Any]) -> str:
    """Serialize an EvalResult to a JSON string."""
    result_data = result.model_dump(mode="json", exclude_none=True)
    data: dict[str, Any] = {"metrics": result_data.get("metrics")}
    if result.result is not None:
        data["result"] = _encode_eval_result_value(result.result)
    return json.dumps(data)


class EvalFunction:
    """A callable wrapper for eval-decorated functions.

    Wraps a function decorated with @bridge_eval, providing access to eval
    metadata and invocation capabilities while preserving the original
    function's call signature.
    """

    def __init__(self, func: Callable[..., Any], eval_data: EvalData) -> None:
        self._func = func
        self.eval_data = eval_data
        self._input_type, self._output_type = _get_context_io_types(func)
        update_wrapper(self, func)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._func(*args, **kwargs)

    async def on_invoke_eval(self, context: str) -> str:
        """Invoke the eval with JSON context and return JSON output.

        Args:
            context: JSON string containing the eval context
                (StepEvalContext or PipelineEvalContext fields).

        Returns:
            JSON string of the EvalResult (metrics + optional result).
        """
        try:
            context_data: dict[str, Any] = json.loads(context) if context else {}
        except Exception as e:
            raise ValueError(
                f"Invalid JSON context for eval {self.eval_data.name}: {context}"
            ) from e

        if self.eval_data.context_type == "step":
            ctx = _build_step_eval_context(
                context_data,
                input_type=self._input_type,
                output_type=self._output_type,
            )
        else:
            ctx = _build_pipeline_eval_context(
                context_data,
                input_type=self._input_type,
                output_type=self._output_type,
            )

        if inspect.iscoroutinefunction(self._func):
            result = await self._func(ctx)
        else:
            result = self._func(ctx)

        if not isinstance(result, EvalResult):
            raise TypeError(
                f"Eval '{self.eval_data.name}' must return an EvalResult, "
                f"got {type(result).__name__}"
            )

        return _serialize_eval_result(result)


def make_eval_function(
    func: Callable[..., Any],
    *,
    name: str | None = None,
    rid: str | None = None,
    description: str | None = None,
) -> EvalFunction:
    """Create an EvalFunction, register it, and return it."""
    data = create_eval_data(func, name=name, rid=rid, description=description)
    eval_function = EvalFunction(func, data)
    EVAL_REGISTRY[data.name] = eval_function
    return eval_function
