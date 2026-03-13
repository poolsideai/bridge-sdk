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

"""Helpers for normalizing eval bindings on steps and pipelines."""

from __future__ import annotations

from typing import TypeAlias

from pydantic import BaseModel

from bridge_sdk.eval_conditions import Condition, always, coerce_condition
from bridge_sdk.eval_function import EvalFunction


class EvalBindingData(BaseModel):
    """Serializable eval binding metadata for DSL output."""

    eval_name: str
    """The name of the eval to run."""

    condition: str
    """CEL expression controlling when the eval runs."""

EvalRef: TypeAlias = EvalFunction | str
EvalBindingSpec: TypeAlias = EvalRef | tuple[EvalRef, Condition | str]


def normalize_eval_bindings(
    eval_bindings: list[EvalBindingSpec] | None,
) -> list[EvalBindingData]:
    """Normalize user-facing eval binding specs into DSL bindings."""
    if not eval_bindings:
        return []

    normalized: list[EvalBindingData] = []
    for spec in eval_bindings:
        if isinstance(spec, tuple):
            if len(spec) != 2:
                raise TypeError(
                    "tuple eval binding entries must be (EvalFunction | str, Condition | str)"
                )
            eval_ref, raw_condition = spec
        else:
            eval_ref, raw_condition = spec, always()

        if isinstance(eval_ref, EvalFunction):
            eval_name = eval_ref.eval_data.name
        elif isinstance(eval_ref, str):
            eval_name = eval_ref
        else:
            raise TypeError(
                "eval_bindings entries must be EvalFunction | str or "
                "tuple[EvalFunction | str, Condition | str], "
                f"got {type(eval_ref).__name__}"
            )

        condition = coerce_condition(raw_condition)
        normalized.append(
            EvalBindingData(
                eval_name=eval_name,
                condition=condition.to_cel(),
            )
        )
    return normalized
