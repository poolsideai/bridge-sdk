"""Tests for the Pipeline class and DSL generation."""

import json
import pytest
from typing import Annotated

from pydantic import BaseModel

from bridge_sdk import (
    Pipeline,
    PipelineData,
    PIPELINE_REGISTRY,
    step,
    step_result,
    STEP_REGISTRY,
)
from bridge_sdk.cli import (
    compute_pipeline_data,
    discover_steps_and_pipelines,
)


# =============================================================================
# Test Models
# =============================================================================


class InputModel(BaseModel):
    value: str


class IntermediateModel(BaseModel):
    processed: str


class OutputModel(BaseModel):
    result: str


class AnotherInputModel(BaseModel):
    count: int


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture(autouse=True)
def clear_registries():
    """Clear both step and pipeline registries before each test."""
    STEP_REGISTRY.clear()
    PIPELINE_REGISTRY.clear()
    yield
    STEP_REGISTRY.clear()
    PIPELINE_REGISTRY.clear()


# =============================================================================
# Pipeline Class Tests
# =============================================================================


class TestPipelineClass:
    """Tests for the Pipeline class instantiation and behavior."""

    def test_pipeline_instantiation_with_required_fields(self):
        """Test that Pipeline can be instantiated with just a name."""
        pipeline = Pipeline(name="test_pipeline")

        assert pipeline.name == "test_pipeline"
        assert pipeline.description is None
        assert pipeline._module_path is None

    def test_pipeline_instantiation_with_all_fields(self):
        """Test that Pipeline can be instantiated with all fields."""
        pipeline = Pipeline(
            name="full_pipeline",
            description="A fully configured pipeline",
        )

        assert pipeline.name == "full_pipeline"
        assert pipeline.description == "A fully configured pipeline"

    def test_pipeline_auto_registration(self):
        """Test that Pipeline instances are auto-registered in PIPELINE_REGISTRY."""
        assert "auto_reg_pipeline" not in PIPELINE_REGISTRY

        pipeline = Pipeline(name="auto_reg_pipeline")

        assert "auto_reg_pipeline" in PIPELINE_REGISTRY
        assert PIPELINE_REGISTRY["auto_reg_pipeline"] is pipeline

    def test_pipeline_repr(self):
        """Test Pipeline string representation."""
        pipeline = Pipeline(name="repr_test", description="Test description")

        repr_str = repr(pipeline)
        assert "Pipeline" in repr_str
        assert "repr_test" in repr_str
        assert "Test description" in repr_str

    def test_multiple_pipelines_registered(self):
        """Test that multiple pipelines can be registered."""
        pipeline1 = Pipeline(name="pipeline_one")
        pipeline2 = Pipeline(name="pipeline_two")

        assert len(PIPELINE_REGISTRY) == 2
        assert "pipeline_one" in PIPELINE_REGISTRY
        assert "pipeline_two" in PIPELINE_REGISTRY

    def test_pipeline_name_override(self):
        """Test that registering a pipeline with same name overrides."""
        pipeline1 = Pipeline(name="override_test", description="First")
        pipeline2 = Pipeline(name="override_test", description="Second")

        assert len(PIPELINE_REGISTRY) == 1
        assert PIPELINE_REGISTRY["override_test"].description == "Second"


# =============================================================================
# PipelineData Model Tests
# =============================================================================


class TestPipelineDataModel:
    """Tests for the PipelineData Pydantic model."""

    def test_pipeline_data_minimal(self):
        """Test PipelineData with minimal required fields."""
        data = PipelineData(
            name="minimal_pipeline",
            module_path="test.module",
        )

        assert data.name == "minimal_pipeline"
        assert data.module_path == "test.module"
        assert data.description is None
        assert data.steps == []
        assert data.dag == {}
        assert data.root_steps == []
        assert data.leaf_steps == []
        assert data.input_json_schema == {}
        assert data.output_json_schema == {}

    def test_pipeline_data_full(self):
        """Test PipelineData with all fields populated."""
        data = PipelineData(
            name="full_pipeline",
            description="A complete pipeline",
            module_path="pipelines.full",
            steps=["step_a", "step_b", "step_c"],
            dag={
                "step_a": [],
                "step_b": ["step_a"],
                "step_c": ["step_b"],
            },
            root_steps=["step_a"],
            leaf_steps=["step_c"],
            input_json_schema={"step_a": {"type": "object"}},
            output_json_schema={"step_c": {"type": "string"}},
        )

        assert data.name == "full_pipeline"
        assert data.description == "A complete pipeline"
        assert len(data.steps) == 3
        assert data.dag["step_b"] == ["step_a"]
        assert data.root_steps == ["step_a"]
        assert data.leaf_steps == ["step_c"]

    def test_pipeline_data_serialization(self):
        """Test that PipelineData can be serialized to JSON."""
        data = PipelineData(
            name="serializable_pipeline",
            module_path="test.serialize",
            steps=["step_x"],
            dag={"step_x": []},
            root_steps=["step_x"],
            leaf_steps=["step_x"],
        )

        # model_dump should return JSON-serializable dict
        dumped = data.model_dump()
        json_str = json.dumps(dumped)

        # Should round-trip correctly
        parsed = json.loads(json_str)
        assert parsed["name"] == "serializable_pipeline"
        assert parsed["steps"] == ["step_x"]


# =============================================================================
# DAG Computation Tests
# =============================================================================


class TestDagComputation:
    """Tests for compute_pipeline_data() function."""

    def test_linear_dag_computation(self):
        """Test DAG computation for a linear pipeline (A -> B -> C)."""
        # Create steps with linear dependencies
        @step(name="step_a")
        def step_a() -> IntermediateModel:
            return IntermediateModel(processed="a")

        @step(name="step_b")
        def step_b(
            input: Annotated[IntermediateModel, step_result("step_a")]
        ) -> IntermediateModel:
            return IntermediateModel(processed="b")

        @step(name="step_c")
        def step_c(
            input: Annotated[IntermediateModel, step_result("step_b")]
        ) -> OutputModel:
            return OutputModel(result="c")

        pipeline = Pipeline(name="linear_pipeline")

        pipeline_data = compute_pipeline_data(
            pipeline=pipeline,
            module_path="test.linear",
            module_steps=["step_a", "step_b", "step_c"],
            step_registry=STEP_REGISTRY,
        )

        assert pipeline_data.name == "linear_pipeline"
        assert set(pipeline_data.steps) == {"step_a", "step_b", "step_c"}
        assert pipeline_data.dag["step_a"] == []
        assert pipeline_data.dag["step_b"] == ["step_a"]
        assert pipeline_data.dag["step_c"] == ["step_b"]
        assert pipeline_data.root_steps == ["step_a"]
        assert pipeline_data.leaf_steps == ["step_c"]

    def test_fan_in_dag_computation(self):
        """Test DAG computation for fan-in pattern (A, B -> C)."""

        @step(name="fan_a")
        def fan_a() -> IntermediateModel:
            return IntermediateModel(processed="a")

        @step(name="fan_b")
        def fan_b() -> IntermediateModel:
            return IntermediateModel(processed="b")

        @step(name="fan_c")
        def fan_c(
            from_a: Annotated[IntermediateModel, step_result("fan_a")],
            from_b: Annotated[IntermediateModel, step_result("fan_b")],
        ) -> OutputModel:
            return OutputModel(result="c")

        pipeline = Pipeline(name="fan_in_pipeline")

        pipeline_data = compute_pipeline_data(
            pipeline=pipeline,
            module_path="test.fan_in",
            module_steps=["fan_a", "fan_b", "fan_c"],
            step_registry=STEP_REGISTRY,
        )

        # Both A and B are root steps (no dependencies)
        assert set(pipeline_data.root_steps) == {"fan_a", "fan_b"}
        # C is the only leaf step
        assert pipeline_data.leaf_steps == ["fan_c"]
        # C depends on both A and B
        assert set(pipeline_data.dag["fan_c"]) == {"fan_a", "fan_b"}

    def test_fan_out_dag_computation(self):
        """Test DAG computation for fan-out pattern (A -> B, C)."""

        @step(name="fanout_a")
        def fanout_a() -> IntermediateModel:
            return IntermediateModel(processed="a")

        @step(name="fanout_b")
        def fanout_b(
            input: Annotated[IntermediateModel, step_result("fanout_a")]
        ) -> OutputModel:
            return OutputModel(result="b")

        @step(name="fanout_c")
        def fanout_c(
            input: Annotated[IntermediateModel, step_result("fanout_a")]
        ) -> OutputModel:
            return OutputModel(result="c")

        pipeline = Pipeline(name="fan_out_pipeline")

        pipeline_data = compute_pipeline_data(
            pipeline=pipeline,
            module_path="test.fan_out",
            module_steps=["fanout_a", "fanout_b", "fanout_c"],
            step_registry=STEP_REGISTRY,
        )

        # A is the only root step
        assert pipeline_data.root_steps == ["fanout_a"]
        # B and C are both leaf steps
        assert set(pipeline_data.leaf_steps) == {"fanout_b", "fanout_c"}

    def test_diamond_dag_computation(self):
        """Test DAG computation for diamond pattern (A -> B, C -> D)."""

        @step(name="diamond_a")
        def diamond_a() -> IntermediateModel:
            return IntermediateModel(processed="a")

        @step(name="diamond_b")
        def diamond_b(
            input: Annotated[IntermediateModel, step_result("diamond_a")]
        ) -> IntermediateModel:
            return IntermediateModel(processed="b")

        @step(name="diamond_c")
        def diamond_c(
            input: Annotated[IntermediateModel, step_result("diamond_a")]
        ) -> IntermediateModel:
            return IntermediateModel(processed="c")

        @step(name="diamond_d")
        def diamond_d(
            from_b: Annotated[IntermediateModel, step_result("diamond_b")],
            from_c: Annotated[IntermediateModel, step_result("diamond_c")],
        ) -> OutputModel:
            return OutputModel(result="d")

        pipeline = Pipeline(name="diamond_pipeline")

        pipeline_data = compute_pipeline_data(
            pipeline=pipeline,
            module_path="test.diamond",
            module_steps=["diamond_a", "diamond_b", "diamond_c", "diamond_d"],
            step_registry=STEP_REGISTRY,
        )

        assert pipeline_data.root_steps == ["diamond_a"]
        assert pipeline_data.leaf_steps == ["diamond_d"]
        assert set(pipeline_data.dag["diamond_d"]) == {"diamond_b", "diamond_c"}

    def test_single_step_pipeline(self):
        """Test DAG computation for a pipeline with a single step."""

        @step(name="solo_step")
        def solo_step(input: InputModel) -> OutputModel:
            return OutputModel(result=input.value)

        pipeline = Pipeline(name="solo_pipeline")

        pipeline_data = compute_pipeline_data(
            pipeline=pipeline,
            module_path="test.solo",
            module_steps=["solo_step"],
            step_registry=STEP_REGISTRY,
        )

        # Single step is both root and leaf
        assert pipeline_data.root_steps == ["solo_step"]
        assert pipeline_data.leaf_steps == ["solo_step"]
        assert pipeline_data.dag["solo_step"] == []


# =============================================================================
# Input/Output Schema Tests
# =============================================================================


class TestSchemaComputation:
    """Tests for input/output schema computation."""

    def test_input_schema_from_root_steps(self):
        """Test that input schemas are derived from root step parameters."""

        @step(name="schema_root")
        def schema_root(input_data: InputModel, count: int) -> IntermediateModel:
            return IntermediateModel(processed=input_data.value)

        @step(name="schema_leaf")
        def schema_leaf(
            data: Annotated[IntermediateModel, step_result("schema_root")]
        ) -> OutputModel:
            return OutputModel(result=data.processed)

        pipeline = Pipeline(name="schema_pipeline")

        pipeline_data = compute_pipeline_data(
            pipeline=pipeline,
            module_path="test.schema",
            module_steps=["schema_root", "schema_leaf"],
            step_registry=STEP_REGISTRY,
        )

        # Input schema should contain root step's params
        assert "schema_root" in pipeline_data.input_json_schema
        root_schema = pipeline_data.input_json_schema["schema_root"]
        assert "properties" in root_schema
        assert "input_data" in root_schema["properties"]
        assert "count" in root_schema["properties"]

        # Leaf step should not be in input schema
        assert "schema_leaf" not in pipeline_data.input_json_schema

    def test_output_schema_from_leaf_steps(self):
        """Test that output schemas are derived from leaf step returns."""

        @step(name="out_root")
        def out_root() -> IntermediateModel:
            return IntermediateModel(processed="root")

        @step(name="out_leaf")
        def out_leaf(
            data: Annotated[IntermediateModel, step_result("out_root")]
        ) -> OutputModel:
            return OutputModel(result=data.processed)

        pipeline = Pipeline(name="output_pipeline")

        pipeline_data = compute_pipeline_data(
            pipeline=pipeline,
            module_path="test.output",
            module_steps=["out_root", "out_leaf"],
            step_registry=STEP_REGISTRY,
        )

        # Output schema should contain leaf step's return
        assert "out_leaf" in pipeline_data.output_json_schema
        # Root step should not be in output schema
        assert "out_root" not in pipeline_data.output_json_schema

    def test_multiple_root_and_leaf_schemas(self):
        """Test schemas with multiple root and leaf steps."""

        @step(name="multi_root_a")
        def multi_root_a(input_a: InputModel) -> IntermediateModel:
            return IntermediateModel(processed="a")

        @step(name="multi_root_b")
        def multi_root_b(input_b: AnotherInputModel) -> IntermediateModel:
            return IntermediateModel(processed="b")

        @step(name="multi_leaf_x")
        def multi_leaf_x(
            data: Annotated[IntermediateModel, step_result("multi_root_a")]
        ) -> OutputModel:
            return OutputModel(result="x")

        @step(name="multi_leaf_y")
        def multi_leaf_y(
            data: Annotated[IntermediateModel, step_result("multi_root_b")]
        ) -> OutputModel:
            return OutputModel(result="y")

        pipeline = Pipeline(name="multi_pipeline")

        pipeline_data = compute_pipeline_data(
            pipeline=pipeline,
            module_path="test.multi",
            module_steps=["multi_root_a", "multi_root_b", "multi_leaf_x", "multi_leaf_y"],
            step_registry=STEP_REGISTRY,
        )

        # Both roots should have input schemas
        assert "multi_root_a" in pipeline_data.input_json_schema
        assert "multi_root_b" in pipeline_data.input_json_schema

        # Both leaves should have output schemas
        assert "multi_leaf_x" in pipeline_data.output_json_schema
        assert "multi_leaf_y" in pipeline_data.output_json_schema


# =============================================================================
# DSL Output Format Tests
# =============================================================================


class TestDslOutputFormat:
    """Tests for the complete DSL output format."""

    def test_dsl_output_structure(self):
        """Test that DSL output has the correct top-level structure."""
        # Create a simple pipeline with steps
        @step(name="dsl_step_a")
        def dsl_step_a() -> IntermediateModel:
            return IntermediateModel(processed="a")

        @step(name="dsl_step_b")
        def dsl_step_b(
            input: Annotated[IntermediateModel, step_result("dsl_step_a")]
        ) -> OutputModel:
            return OutputModel(result="b")

        pipeline = Pipeline(name="dsl_test_pipeline", description="Test pipeline")

        pipeline_data = compute_pipeline_data(
            pipeline=pipeline,
            module_path="test.dsl",
            module_steps=["dsl_step_a", "dsl_step_b"],
            step_registry=STEP_REGISTRY,
        )

        # Build the full DSL output structure
        dsl_output = {
            "steps": {
                name: STEP_REGISTRY[name].step_data.model_dump()
                for name in ["dsl_step_a", "dsl_step_b"]
            },
            "pipelines": {
                "dsl_test_pipeline": pipeline_data.model_dump()
            },
        }

        # Verify structure
        assert "steps" in dsl_output
        assert "pipelines" in dsl_output

        # Verify steps content
        assert "dsl_step_a" in dsl_output["steps"]
        assert "dsl_step_b" in dsl_output["steps"]
        assert "depends_on" in dsl_output["steps"]["dsl_step_a"]
        assert "depends_on" in dsl_output["steps"]["dsl_step_b"]

        # Verify pipeline content
        pipeline_output = dsl_output["pipelines"]["dsl_test_pipeline"]
        assert pipeline_output["name"] == "dsl_test_pipeline"
        assert pipeline_output["description"] == "Test pipeline"
        assert "dag" in pipeline_output
        assert "root_steps" in pipeline_output
        assert "leaf_steps" in pipeline_output
        assert "input_json_schema" in pipeline_output
        assert "output_json_schema" in pipeline_output

    def test_dsl_output_json_serializable(self):
        """Test that the complete DSL output is JSON serializable."""

        @step(name="json_step")
        def json_step(data: InputModel) -> OutputModel:
            return OutputModel(result=data.value)

        pipeline = Pipeline(name="json_pipeline")

        pipeline_data = compute_pipeline_data(
            pipeline=pipeline,
            module_path="test.json",
            module_steps=["json_step"],
            step_registry=STEP_REGISTRY,
        )

        dsl_output = {
            "steps": {
                "json_step": STEP_REGISTRY["json_step"].step_data.model_dump()
            },
            "pipelines": {
                "json_pipeline": pipeline_data.model_dump()
            },
        }

        # Should not raise
        json_str = json.dumps(dsl_output, indent=2)
        assert len(json_str) > 0

        # Should round-trip
        parsed = json.loads(json_str)
        assert parsed["pipelines"]["json_pipeline"]["name"] == "json_pipeline"


# =============================================================================
# Integration Tests
# =============================================================================


class TestPipelineIntegration:
    """Integration tests for the complete pipeline workflow."""

    def test_pipeline_with_step_object_references(self):
        """Test that step_result works with StepFunction objects."""

        @step(name="ref_source")
        def ref_source() -> IntermediateModel:
            return IntermediateModel(processed="source")

        @step(name="ref_target")
        def ref_target(
            # Reference the step object directly, not by name string
            data: Annotated[IntermediateModel, step_result(ref_source)]
        ) -> OutputModel:
            return OutputModel(result=data.processed)

        pipeline = Pipeline(name="ref_pipeline")

        pipeline_data = compute_pipeline_data(
            pipeline=pipeline,
            module_path="test.ref",
            module_steps=["ref_source", "ref_target"],
            step_registry=STEP_REGISTRY,
        )

        # The dependency should be correctly resolved to "ref_source"
        assert "ref_source" in pipeline_data.dag["ref_target"]

    def test_empty_pipeline(self):
        """Test pipeline with no steps in the module."""
        pipeline = Pipeline(name="empty_pipeline")

        pipeline_data = compute_pipeline_data(
            pipeline=pipeline,
            module_path="test.empty",
            module_steps=[],
            step_registry=STEP_REGISTRY,
        )

        assert pipeline_data.name == "empty_pipeline"
        assert pipeline_data.steps == []
        assert pipeline_data.dag == {}
        assert pipeline_data.root_steps == []
        assert pipeline_data.leaf_steps == []

    def test_pipeline_any_variable_name(self):
        """Test that Pipeline can be assigned to any variable name."""
        # Use a non-standard variable name
        my_custom_pipeline_name = Pipeline(
            name="custom_named_pipeline",
            description="Pipeline with custom variable name"
        )

        assert "custom_named_pipeline" in PIPELINE_REGISTRY
        assert PIPELINE_REGISTRY["custom_named_pipeline"] is my_custom_pipeline_name
        assert my_custom_pipeline_name.name == "custom_named_pipeline"


# =============================================================================
# Module Discovery Tests
# =============================================================================


class TestModuleDiscovery:
    """Tests for pipeline discovery from modules."""

    def test_discover_pipeline_from_module(self):
        """Test that discover_steps_and_pipelines finds Pipeline instances."""
        # This test uses the examples.agent_example module
        steps, pipelines = discover_steps_and_pipelines(["examples.agent_example"])

        # Should find at least one pipeline
        assert len(pipelines) >= 1

        # The agent_example pipeline should be found
        assert "agent_example" in pipelines
        pipeline, module_path, module_steps = pipelines["agent_example"]
        assert pipeline.name == "agent_example"
        assert module_path == "examples.agent_example"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

