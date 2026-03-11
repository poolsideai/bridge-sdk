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

"""@bridge_eval decorator for defining eval functions."""

from typing import Any, Callable, overload

from bridge_sdk.eval_function import EvalFunction, make_eval_function


@overload
def bridge_eval(
    func: Callable[..., Any],
    *,
    name: str | None = None,
    rid: str | None = None,
    description: str | None = None,
) -> EvalFunction:
    """Overload for usage as @bridge_eval (no parentheses)."""
    ...


@overload
def bridge_eval(
    *,
    name: str | None = None,
    rid: str | None = None,
    description: str | None = None,
) -> Callable[[Callable[..., Any]], EvalFunction]:
    """Overload for usage as @bridge_eval(...)"""
    ...


def bridge_eval(
    func: Callable[..., Any] | None = None,
    *,
    name: str | None = None,
    rid: str | None = None,
    description: str | None = None,
) -> EvalFunction | Callable[[Callable[..., Any]], EvalFunction]:
    """Decorator for defining an eval function.

    Supports both ``@bridge_eval`` and ``@bridge_eval(...)`` usage.

    The decorated function must accept a ``StepEvalContext`` or
    ``PipelineEvalContext`` as its first parameter and return an
    ``EvalResult``.

    Args:
        func: The function to decorate (when used without parentheses).
        name: Optional override name for the eval. Defaults to function name.
        rid: Optional stable resource identifier (UUID).
        description: Optional human-readable description.

    Returns:
        An EvalFunction wrapper with eval_data attribute.
    """

    def _create_eval_function(the_func: Callable[..., Any]) -> EvalFunction:
        return make_eval_function(
            the_func,
            name=name,
            rid=rid,
            description=description,
        )

    if callable(func):
        return _create_eval_function(func)

    return _create_eval_function
