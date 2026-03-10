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

"""@evaluated_by decorator for binding evals to steps and pipelines."""

from __future__ import annotations

from typing import Any, Callable

from pydantic import BaseModel

from bridge_sdk.eval_conditions import Condition, always, coerce_condition
from bridge_sdk.eval_function import EvalFunction


class EvalBindingData(BaseModel):
    """Serializable eval binding metadata for DSL output."""

    eval_name: str
    """The name of the eval to run."""

    condition: str
    """CEL expression controlling when the eval runs."""


def evaluated_by(
    eval_ref: EvalFunction | str,
    *,
    when: Condition | str | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that binds an eval to a step or pipeline.

    Must be applied **below** ``@step`` (i.e., closer to the function
    definition), since Python applies decorators bottom-up::

        @step                          # applied second
        @evaluated_by(my_eval)         # applied first
        def my_step(...): ...

    Args:
        eval_ref: The eval to bind. Either an ``EvalFunction`` or a string
            name (for cross-repo references).
        when: CEL condition controlling when the eval runs. Accepts either a
            :class:`Condition` helper value or a raw CEL expression string.
            Defaults to ``always()``.

    Returns:
        A decorator that attaches eval binding metadata to the function.

    Raises:
        TypeError: If applied after ``@step`` (receives a ``StepFunction``
            instead of a raw function).
    """
    condition = coerce_condition(when or always())

    if isinstance(eval_ref, EvalFunction):
        eval_name = eval_ref.eval_data.name
    elif isinstance(eval_ref, str):
        eval_name = eval_ref
    else:
        raise TypeError(
            f"evaluated_by() expects an EvalFunction or string name, "
            f"got {type(eval_ref).__name__}"
        )

    binding = EvalBindingData(
        eval_name=eval_name,
        condition=condition.to_cel(),
    )

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # Import here to avoid circular import (step_data → eval_binding → step_function)
        from bridge_sdk.step_function import StepFunction

        if isinstance(func, StepFunction):
            raise TypeError(
                "evaluated_by() must be applied before @step. "
                "Reorder your decorators so @evaluated_by is below @step:\n\n"
                "    @step\n"
                "    @evaluated_by(...)\n"
                "    def my_step(...): ..."
            )

        bindings: list[EvalBindingData] = getattr(func, "_eval_bindings", [])
        bindings.append(binding)
        func._eval_bindings = bindings  # type: ignore[attr-defined]
        return func

    return decorator
