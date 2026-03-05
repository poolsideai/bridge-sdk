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

"""Core types for Bridge evals: contexts, results, and metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar

I = TypeVar("I")
O = TypeVar("O")
M = TypeVar("M")


@dataclass
class EvalResult(Generic[M]):
    """Result returned by an eval function.

    Args:
        metrics: Structured metrics matching the eval's metrics schema.
        output: Optional unstructured text output (e.g., LLM judge reasoning).
    """

    metrics: M
    output: str | None = None


@dataclass
class StepMetadata:
    """Metadata about the step execution being evaluated."""

    step_rid: str
    step_version_id: str
    execution_id: str
    repository: str
    branch: str
    commit_sha: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int


@dataclass
class StepEvalContext(Generic[I, O]):
    """Context provided to step-level eval functions.

    Args:
        step_name: Name of the step that was executed.
        step_input: The input that was passed to the step.
        step_output: The output produced by the step.
        trajectory: Full agent trajectory for agentic steps, or None.
        metadata: Execution metadata (rid, branch, timing, etc.).
    """

    step_name: str
    step_input: I
    step_output: O
    trajectory: Any | None
    metadata: StepMetadata


@dataclass
class StepResult:
    """Result of an individual step within a pipeline evaluation."""

    step_name: str
    input: Any
    output: Any
    trajectory: Any | None
    duration_ms: int
    success: bool


@dataclass
class PipelineMetadata:
    """Metadata about the pipeline execution being evaluated."""

    pipeline_rid: str
    pipeline_version_id: str
    run_id: str
    repository: str
    branch: str
    commit_sha: str
    started_at: datetime
    completed_at: datetime
    duration_ms: int


@dataclass
class PipelineEvalContext(Generic[I, O]):
    """Context provided to pipeline-level eval functions.

    Args:
        pipeline_name: Name of the pipeline that was executed.
        pipeline_input: The inputs to the pipeline.
        pipeline_output: The outputs from the pipeline.
        steps: Results of individual steps, keyed by step name.
        metadata: Execution metadata (rid, branch, timing, etc.).
    """

    pipeline_name: str
    pipeline_input: I
    pipeline_output: O
    steps: dict[str, StepResult] = field(default_factory=dict)
    metadata: PipelineMetadata | None = None
