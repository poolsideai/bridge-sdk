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

"""Composable conditions for controlling when evals run."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Condition(ABC):
    """Base class for eval execution conditions.

    Conditions control when an eval is executed. They can be combined
    using ``&`` (and) and ``|`` (or) operators::

        on_branch("main") & sample(0.1)
        on_branch("main") | on_branch("staging")
    """

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize this condition to a JSON-compatible dict."""
        ...

    def __and__(self, other: Condition) -> Condition:
        left = self._flat_conditions("and")
        right = other._flat_conditions("and")
        return _AndCondition(left + right)

    def __or__(self, other: Condition) -> Condition:
        left = self._flat_conditions("or")
        right = other._flat_conditions("or")
        return _OrCondition(left + right)

    def _flat_conditions(self, kind: str) -> list[Condition]:
        """Return a flat list of conditions for combining.

        If this condition is already the same combinator kind, return its
        children to avoid unnecessary nesting.
        """
        return [self]


class _AlwaysCondition(Condition):
    def to_dict(self) -> dict[str, Any]:
        return {"type": "always"}


class _NeverCondition(Condition):
    def to_dict(self) -> dict[str, Any]:
        return {"type": "never"}


class _BranchCondition(Condition):
    def __init__(self, branch: str) -> None:
        self.branch = branch

    def to_dict(self) -> dict[str, Any]:
        return {"type": "branch", "branch": self.branch}


class _SampleCondition(Condition):
    def __init__(self, rate: float) -> None:
        if not 0.0 <= rate <= 1.0:
            raise ValueError(f"sample rate must be between 0.0 and 1.0, got {rate}")
        self.rate = rate

    def to_dict(self) -> dict[str, Any]:
        return {"type": "sample", "rate": self.rate}


class _AndCondition(Condition):
    def __init__(self, conditions: list[Condition]) -> None:
        self.conditions = conditions

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "and",
            "conditions": [c.to_dict() for c in self.conditions],
        }

    def _flat_conditions(self, kind: str) -> list[Condition]:
        if kind == "and":
            return list(self.conditions)
        return [self]


class _OrCondition(Condition):
    def __init__(self, conditions: list[Condition]) -> None:
        self.conditions = conditions

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "or",
            "conditions": [c.to_dict() for c in self.conditions],
        }

    def _flat_conditions(self, kind: str) -> list[Condition]:
        if kind == "or":
            return list(self.conditions)
        return [self]


def always() -> Condition:
    """Condition that always passes. This is the default."""
    return _AlwaysCondition()


def never() -> Condition:
    """Condition that never passes."""
    return _NeverCondition()


def on_branch(branch: str) -> Condition:
    """Condition that passes when executing on the given branch."""
    return _BranchCondition(branch)


def sample(rate: float) -> Condition:
    """Condition that passes for a random sample of executions.

    Args:
        rate: Sampling rate between 0.0 and 1.0 (e.g., 0.1 = 10%).
    """
    return _SampleCondition(rate)
