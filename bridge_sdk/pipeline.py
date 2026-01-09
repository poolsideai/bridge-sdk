"""Pipeline module for defining pipelines as first-class entities."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# Registry for discovered pipelines
PIPELINE_REGISTRY: Dict[str, "Pipeline"] = {}


class Pipeline:
    """Defines a pipeline as a first-class entity within a module.

    A pipeline is defined as a Python module containing:
    1. A single `Pipeline` instance (any variable name)
    2. `@step` decorated functions with `step_result` dependencies

    The DAG is implicit via `step_result` annotations on step parameters.
    Each module can contain at most one Pipeline instance.

    Usage:
        # pipelines/doc_eval.py
        from bridge_sdk import Pipeline, step

        my_pipeline = Pipeline(
            name="doc_eval",
            description="Evaluate document processing quality",
        )

        @step
        def load_dataset(input: DocInput) -> DataOutput: ...

        @step
        def run_inference(
            data: Annotated[DataOutput, step_result(load_dataset)]
        ) -> InferenceOutput: ...

    Attributes:
        name: The unique name of the pipeline.
        description: Optional human-readable description.
    """

    def __init__(
        self,
        name: str,
        description: str | None = None,
    ):
        """Initialize a Pipeline.

        Args:
            name: The unique name of the pipeline.
            description: Optional human-readable description.
        """
        self.name = name
        self.description = description
        self._module_path: str | None = None  # Set during discovery

        # Auto-register this pipeline
        PIPELINE_REGISTRY[name] = self

    def __repr__(self) -> str:
        return f"Pipeline(name={self.name!r}, description={self.description!r})"


class PipelineData(BaseModel):
    """Serializable pipeline metadata for DSL output.

    This model represents all the metadata needed by the backend to
    index and execute a pipeline.

    Attributes:
        name: The unique name of the pipeline.
        description: Optional human-readable description.
        module_path: The Python module path (e.g., "pipelines.doc_eval").
        steps: List of step names defined in this pipeline's module.
        dag: Mapping of step_name -> list of dependency step names.
        root_steps: Steps with no step_result dependencies (pipeline inputs).
        leaf_steps: Steps with no dependents (pipeline outputs).
        input_json_schema: {step_name: params_schema} for root steps.
        output_json_schema: {step_name: return_schema} for leaf steps.
    """

    name: str
    """The unique name of the pipeline."""

    description: Optional[str] = None
    """Optional human-readable description."""

    module_path: str
    """The Python module path (e.g., 'pipelines.doc_eval')."""

    steps: List[str] = Field(default_factory=list)
    """List of step names defined in this pipeline's module."""

    dag: Dict[str, List[str]] = Field(default_factory=dict)
    """Mapping of step_name -> list of dependency step names."""

    root_steps: List[str] = Field(default_factory=list)
    """Steps with no step_result dependencies (pipeline inputs)."""

    leaf_steps: List[str] = Field(default_factory=list)
    """Steps with no dependents (pipeline outputs)."""

    input_json_schema: Dict[str, Any] = Field(default_factory=dict)
    """Input schemas for root steps: {step_name: params_json_schema}."""

    output_json_schema: Dict[str, Any] = Field(default_factory=dict)
    """Output schemas for leaf steps: {step_name: return_json_schema}."""
