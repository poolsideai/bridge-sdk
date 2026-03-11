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

"""Composable CEL conditions for controlling when evals run."""

from __future__ import annotations

import json


def _to_cel_string_literal(value: str) -> str:
    return json.dumps(value)


class Condition:
    """CEL expression wrapper with composition helpers.

    Conditions can be combined using ``&`` (and) and ``|`` (or)::

        on_branch("main") & sample(0.1)
        on_branch("main") | on_branch("staging")
    """

    def __init__(self, expression: str) -> None:
        if expression == "":
            raise ValueError("condition expression must not be empty")
        self._expression = expression

    def to_cel(self) -> str:
        return self._expression

    def __str__(self) -> str:
        return self._expression

    def __and__(self, other: Condition | str) -> Condition:
        rhs = coerce_condition(other)
        return Condition(f"({self.to_cel()}) && ({rhs.to_cel()})")

    def __or__(self, other: Condition | str) -> Condition:
        rhs = coerce_condition(other)
        return Condition(f"({self.to_cel()}) || ({rhs.to_cel()})")


def coerce_condition(condition: Condition | str) -> Condition:
    if isinstance(condition, Condition):
        return condition
    if isinstance(condition, str):
        return Condition(condition)
    raise TypeError(f"condition must be Condition or str, got {type(condition).__name__}")


def always() -> Condition:
    """Condition that always passes. This is the default."""
    return Condition("true")


def never() -> Condition:
    """Condition that never passes."""
    return Condition("false")


def on_branch(branch: str) -> Condition:
    """Condition that passes when executing on the given branch."""
    return Condition(f"metadata.branch == {_to_cel_string_literal(branch)}")


def sample(rate: float) -> Condition:
    """Condition that passes for a deterministic sample of executions.

    Args:
        rate: Sampling rate between 0.0 and 1.0 (e.g., 0.1 = 10%).
    """
    if not 0.0 <= rate <= 1.0:
        raise ValueError(f"sample rate must be between 0.0 and 1.0, got {rate}")
    return Condition(f"sample_value < {rate!r}")
