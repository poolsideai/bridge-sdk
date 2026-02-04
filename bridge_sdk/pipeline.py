"""Pipeline module for defining pipelines as first-class entities."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, overload

from pydantic import BaseModel
from typing_extensions import ParamSpec, TypeVar

from bridge_sdk.step_function import StepFunction, make_step_function

P = ParamSpec("P")
R = TypeVar("R")


# Registry for discovered pipelines
PIPELINE_REGISTRY: Dict[str, "Pipeline"] = {}


class Pipeline:
    """Defines a pipeline as a first-class entity within a module.

    A pipeline groups steps together via the ``@pipeline.step`` decorator.
    The DAG is implicit via ``step_result`` annotations on step parameters.

    Usage:
        # pipelines/doc_eval.py
        from bridge_sdk import Pipeline

        pipeline = Pipeline(
            name="doc_eval",
            description="Evaluate document processing quality",
        )

        @pipeline.step
        def load_dataset(input: DocInput) -> DataOutput: ...

        @pipeline.step
        def run_inference(
            data: Annotated[DataOutput, step_result(load_dataset)]
        ) -> InferenceOutput: ...

    Attributes:
        name: The unique name of the pipeline.
        rid: Optional stable resource identifier (UUID).
        description: Optional human-readable description.
    """

    def __init__(
        self,
        name: str,
        rid: str | None = None,
        description: str | None = None,
    ):
        """Initialize a Pipeline.

        Args:
            name: The unique name of the pipeline.
            rid: Optional stable resource identifier (UUID). If provided, the
                backend will use this rid instead of generating a new one.
                This enables renaming pipelines while preserving their identity.
            description: Optional human-readable description.
        """
        self.name = name
        self.rid = rid
        self.description = description
        # Auto-register this pipeline
        PIPELINE_REGISTRY[name] = self

    @overload
    def step(
        self,
        func: Callable[P, R],
        *,
        name: str | None = ...,
        rid: str | None = ...,
        description: str | None = ...,
        setup_script: str | None = ...,
        post_execution_script: str | None = ...,
        metadata: dict[str, Any] | None = ...,
        sandbox_id: str | None = ...,
        credential_bindings: dict[str, str] | None = ...,
    ) -> StepFunction[P, R]:
        """Overload for usage as @pipeline.step (no parentheses)."""
        ...

    @overload
    def step(
        self,
        *,
        name: str | None = ...,
        rid: str | None = ...,
        description: str | None = ...,
        setup_script: str | None = ...,
        post_execution_script: str | None = ...,
        metadata: dict[str, Any] | None = ...,
        sandbox_id: str | None = ...,
        credential_bindings: dict[str, str] | None = ...,
    ) -> Callable[[Callable[P, R]], StepFunction[P, R]]:
        """Overload for usage as @pipeline.step(...)"""
        ...

    def step(
        self,
        func: Callable[P, R] | None = None,
        *,
        name: str | None = None,
        rid: str | None = None,
        description: str | None = None,
        setup_script: str | None = None,
        post_execution_script: str | None = None,
        metadata: dict[str, Any] | None = None,
        sandbox_id: str | None = None,
        credential_bindings: dict[str, str] | None = None,
    ) -> StepFunction[P, R] | Callable[[Callable[P, R]], StepFunction[P, R]]:
        """Decorator for defining a step associated with this pipeline.

        Supports ``@pipeline.step``, ``@pipeline.step()``, and
        ``@pipeline.step(name=..., ...)``.
        """
        def _create(the_func: Callable[P, R]) -> StepFunction[P, R]:
            sf = make_step_function(
                the_func,
                name=name,
                rid=rid,
                description=description,
                setup_script=setup_script,
                post_execution_script=post_execution_script,
                metadata=metadata,
                sandbox_id=sandbox_id,
                credential_bindings=credential_bindings,
                pipeline_name=self.name,
            )
            return sf

        if callable(func):
            return _create(func)
        return _create

    def __repr__(self) -> str:
        return f"Pipeline(name={self.name!r}, rid={self.rid!r}, description={self.description!r})"


class PipelineData(BaseModel):
    """Serializable pipeline metadata for DSL output.

    This model represents the metadata needed by the backend to
    identify a pipeline. Step-to-pipeline association is tracked
    via the ``pipeline`` field on each :class:`StepData`.

    Attributes:
        name: The unique name of the pipeline.
        rid: Optional stable resource identifier (UUID).
        description: Optional human-readable description.
    """

    name: str
    """The unique name of the pipeline."""

    rid: Optional[str] = None
    """Optional stable resource identifier (UUID). If provided, the backend
    will use this rid instead of generating a new one."""

    description: Optional[str] = None
    """Optional human-readable description."""
