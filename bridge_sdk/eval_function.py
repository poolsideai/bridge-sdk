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
import re
from datetime import datetime
from functools import update_wrapper
from typing import Any, Callable, Dict, get_args, get_type_hints

from pydantic import TypeAdapter

from bridge_sdk.eval_data import EvalData, create_eval_data
from bridge_sdk.eval_types import (
    EvalResult,
    PipelineEvalContext,
    PipelineMetadata,
    StepEvalContext,
    StepMetadata,
    StepResult,
)

EVAL_REGISTRY: Dict[str, "EvalFunction"] = {}

_RFC3339_PATTERN = re.compile(
    r"^(?P<prefix>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})"
    r"(?:\.(?P<fraction>\d+))?"
    r"(?P<suffix>Z|[+-]\d{2}:\d{2})?$"
)


def _parse_datetime(value: Any) -> datetime:
    """Parse a datetime from a string or return as-is if already a datetime."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        match = _RFC3339_PATTERN.match(value)
        if match:
            prefix = match.group("prefix")
            fraction = match.group("fraction")
            suffix = match.group("suffix")
            if fraction:
                # Python datetime supports at most microsecond precision.
                fraction = fraction[:6]
                prefix = f"{prefix}.{fraction}"
            if suffix == "Z":
                suffix = "+00:00"
            value = f"{prefix}{suffix or ''}"
        return datetime.fromisoformat(value)
    raise TypeError(f"Cannot parse datetime from {type(value)}: {value}")


def _is_any(tp: Any) -> bool:
    """Check if a type annotation is Any."""
    return tp is Any


def _deserialize_value(value: Any, tp: Any, field_name: str) -> Any:
    """Deserialize a value according to the target type annotation."""
    if _is_any(tp):
        return value
    try:
        return TypeAdapter(tp).validate_python(value)
    except Exception as e:
        raise TypeError(
            f"Failed to deserialize '{field_name}' as {tp!r}: {e}"
        ) from e


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
    if len(ctx_args) >= 2:
        return ctx_args[0], ctx_args[1]
    return Any, Any


def _build_step_eval_context(
    data: dict[str, Any],
    input_type: Any = Any,
    output_type: Any = Any,
) -> StepEvalContext[Any, Any]:
    """Build a StepEvalContext from a deserialized JSON dict."""
    metadata_raw = data.get("metadata", {})
    metadata = StepMetadata(
        step_rid=metadata_raw.get("step_rid", ""),
        step_version_id=metadata_raw.get("step_version_id", ""),
        execution_id=metadata_raw.get("execution_id", ""),
        repository=metadata_raw.get("repository", ""),
        branch=metadata_raw.get("branch", ""),
        commit_sha=metadata_raw.get("commit_sha", ""),
        started_at=_parse_datetime(
            metadata_raw.get("started_at") or "1970-01-01T00:00:00"
        ),
        completed_at=_parse_datetime(
            metadata_raw.get("completed_at") or "1970-01-01T00:00:00"
        ),
        duration_ms=metadata_raw.get("duration_ms", 0),
    )
    return StepEvalContext(
        step_name=data.get("step_name", ""),
        step_input=_deserialize_value(
            data.get("step_input"),
            input_type,
            "step_input",
        ),
        step_output=_deserialize_value(
            data.get("step_output"),
            output_type,
            "step_output",
        ),
        trajectory=data.get("trajectory"),
        metadata=metadata,
    )


def _build_pipeline_eval_context(
    data: dict[str, Any],
    input_type: Any = Any,
    output_type: Any = Any,
) -> PipelineEvalContext[Any, Any]:
    """Build a PipelineEvalContext from a deserialized JSON dict."""
    metadata_raw = data.get("metadata")
    metadata = None
    if metadata_raw:
        metadata = PipelineMetadata(
            pipeline_rid=metadata_raw.get("pipeline_rid", ""),
            pipeline_version_id=metadata_raw.get("pipeline_version_id", ""),
            run_id=metadata_raw.get("run_id", ""),
            repository=metadata_raw.get("repository", ""),
            branch=metadata_raw.get("branch", ""),
            commit_sha=metadata_raw.get("commit_sha", ""),
            started_at=_parse_datetime(
                metadata_raw.get("started_at") or "1970-01-01T00:00:00"
            ),
            completed_at=_parse_datetime(
                metadata_raw.get("completed_at") or "1970-01-01T00:00:00"
            ),
            duration_ms=metadata_raw.get("duration_ms", 0),
        )

    steps_raw = data.get("steps", {})
    steps = {
        name: StepResult(
            step_name=sr.get("step_name", name),
            input=sr.get("input"),
            output=sr.get("output"),
            trajectory=sr.get("trajectory"),
            duration_ms=sr.get("duration_ms", 0),
            success=sr.get("success", True),
        )
        for name, sr in steps_raw.items()
    }

    return PipelineEvalContext(
        pipeline_name=data.get("pipeline_name", ""),
        pipeline_input=_deserialize_value(
            data.get("pipeline_input"),
            input_type,
            "pipeline_input",
        ),
        pipeline_output=_deserialize_value(
            data.get("pipeline_output"),
            output_type,
            "pipeline_output",
        ),
        steps=steps,
        metadata=metadata,
    )


def _serialize_eval_result(result: EvalResult[Any]) -> str:
    """Serialize an EvalResult to a JSON string."""
    data: dict[str, Any] = {"metrics": result.metrics}
    if result.output is not None:
        data["output"] = result.output
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
            JSON string of the EvalResult (metrics + optional output).
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
