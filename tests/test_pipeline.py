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
        _pipeline1 = Pipeline(name="pipeline_one")
        _pipeline2 = Pipeline(name="pipeline_two")

        assert len(PIPELINE_REGISTRY) == 2
        assert "pipeline_one" in PIPELINE_REGISTRY
        assert "pipeline_two" in PIPELINE_REGISTRY

    def test_pipeline_name_override(self):
        """Test that registering a pipeline with same name overrides."""
        _pipeline1 = Pipeline(name="override_test", description="First")
        _pipeline2 = Pipeline(name="override_test", description="Second")

        assert len(PIPELINE_REGISTRY) == 1
        assert PIPELINE_REGISTRY["override_test"].description == "Second"

    def test_pipeline_with_rid(self):
        """Test that Pipeline can be instantiated with a rid."""
        pipeline = Pipeline(
            name="rid_test_pipeline",
            rid="550e8400-e29b-41d4-a716-446655440000",
            description="Pipeline with rid",
        )

        assert pipeline.name == "rid_test_pipeline"
        assert pipeline.rid == "550e8400-e29b-41d4-a716-446655440000"
        assert pipeline.description == "Pipeline with rid"

    def test_pipeline_rid_in_repr(self):
        """Test Pipeline repr includes rid."""
        pipeline = Pipeline(
            name="repr_rid_test",
            rid="test-rid-123",
        )

        repr_str = repr(pipeline)
        assert "test-rid-123" in repr_str


# =============================================================================
# PipelineData Model Tests
# =============================================================================


class TestPipelineDataModel:
    """Tests for the PipelineData Pydantic model."""

    def test_pipeline_data_minimal(self):
        """Test PipelineData with minimal required fields."""
        data = PipelineData(name="minimal_pipeline")

        assert data.name == "minimal_pipeline"
        assert data.description is None
        assert data.rid is None

    def test_pipeline_data_full(self):
        """Test PipelineData with all fields populated."""
        data = PipelineData(
            name="full_pipeline",
            rid="test-rid",
            description="A complete pipeline",
        )

        assert data.name == "full_pipeline"
        assert data.rid == "test-rid"
        assert data.description == "A complete pipeline"

    def test_pipeline_data_serialization(self):
        """Test that PipelineData can be serialized to JSON."""
        data = PipelineData(
            name="serializable_pipeline",
            description="test",
        )

        dumped = data.model_dump()
        json_str = json.dumps(dumped)

        parsed = json.loads(json_str)
        assert parsed["name"] == "serializable_pipeline"
        # Stripped-down PipelineData should not have dag, steps, etc.
        assert "dag" not in parsed
        assert "steps" not in parsed
        assert "root_steps" not in parsed
        assert "leaf_steps" not in parsed
        assert "input_json_schema" not in parsed
        assert "output_json_schema" not in parsed
        assert "module_path" not in parsed

    def test_pipeline_data_with_rid(self):
        """Test that PipelineData includes rid when provided."""
        data = PipelineData(
            name="rid_pipeline",
            rid="550e8400-e29b-41d4-a716-446655440000",
        )

        assert data.rid == "550e8400-e29b-41d4-a716-446655440000"

        dumped = data.model_dump()
        assert dumped["rid"] == "550e8400-e29b-41d4-a716-446655440000"

    def test_pipeline_data_rid_optional(self):
        """Test that PipelineData rid is optional and defaults to None."""
        data = PipelineData(name="no_rid_pipeline")
        assert data.rid is None


# =============================================================================
# Pipeline.step() Decorator Tests
# =============================================================================


class TestPipelineStepDecorator:
    """Tests for the @pipeline.step decorator."""

    def test_pipeline_step_no_parens(self):
        """Test @pipeline.step with no parentheses."""
        pipeline = Pipeline(name="no_parens_pipeline")

        @pipeline.step
        def my_step() -> str:
            return "test"

        assert "my_step" in STEP_REGISTRY
        assert STEP_REGISTRY["my_step"].step_data.pipeline == "no_parens_pipeline"

    def test_pipeline_step_empty_parens(self):
        """Test @pipeline.step() with empty parentheses."""
        pipeline = Pipeline(name="empty_parens_pipeline")

        @pipeline.step()
        def my_step() -> str:
            return "test"

        assert "my_step" in STEP_REGISTRY
        assert STEP_REGISTRY["my_step"].step_data.pipeline == "empty_parens_pipeline"

    def test_pipeline_step_with_kwargs(self):
        """Test @pipeline.step(name=..., ...) with keyword arguments."""
        pipeline = Pipeline(name="kwargs_pipeline")

        @pipeline.step(
            name="custom_name",
            rid="test-rid",
            description="A test step",
            setup_script="setup.sh",
            post_execution_script="cleanup.sh",
            metadata={"type": "test"},
        )
        def my_step() -> str:
            return "test"

        assert "custom_name" in STEP_REGISTRY
        sd = STEP_REGISTRY["custom_name"].step_data
        assert sd.pipeline == "kwargs_pipeline"
        assert sd.rid == "test-rid"
        assert sd.description == "A test step"
        assert sd.setup_script == "setup.sh"
        assert sd.post_execution_script == "cleanup.sh"
        assert sd.metadata == {"type": "test"}

    def test_pipeline_step_data_pipeline_field(self):
        """Test that step_data.pipeline is correctly set."""
        pipeline = Pipeline(name="field_test_pipeline")

        @pipeline.step
        def step_a() -> str:
            return "a"

        @pipeline.step()
        def step_b() -> str:
            return "b"

        assert STEP_REGISTRY["step_a"].step_data.pipeline == "field_test_pipeline"
        assert STEP_REGISTRY["step_b"].step_data.pipeline == "field_test_pipeline"

    def test_pipeline_steps_in_registry(self):
        """Test that pipeline steps are discoverable via STEP_REGISTRY."""
        pipeline = Pipeline(name="tracking_pipeline")

        @pipeline.step
        def step_one() -> str:
            return "one"

        @pipeline.step(name="step_two_custom")
        def step_two() -> str:
            return "two"

        pipeline_steps = [
            name for name, sf in STEP_REGISTRY.items()
            if sf.step_data.pipeline == "tracking_pipeline"
        ]
        assert set(pipeline_steps) == {"step_one", "step_two_custom"}

    def test_pipeline_step_with_dependencies(self):
        """Test @pipeline.step with step_result dependencies."""
        pipeline = Pipeline(name="dep_pipeline")

        @pipeline.step
        def root_step() -> IntermediateModel:
            return IntermediateModel(processed="root")

        @pipeline.step
        def child_step(
            data: Annotated[IntermediateModel, step_result(root_step)],
        ) -> OutputModel:
            return OutputModel(result=data.processed)

        assert STEP_REGISTRY["root_step"].step_data.pipeline == "dep_pipeline"
        assert STEP_REGISTRY["child_step"].step_data.pipeline == "dep_pipeline"
        assert "root_step" in STEP_REGISTRY["child_step"].step_data.depends_on

    def test_pipeline_step_callable(self):
        """Test that @pipeline.step decorated functions are still callable."""
        pipeline = Pipeline(name="callable_pipeline")

        @pipeline.step
        def add(a: int, b: int) -> int:
            return a + b

        assert add(1, 2) == 3

    def test_multiple_pipelines_in_module(self):
        """Test that multiple pipelines can coexist and each tracks its own steps."""
        pipeline_a = Pipeline(name="pipeline_a")
        pipeline_b = Pipeline(name="pipeline_b")

        @pipeline_a.step
        def step_for_a() -> str:
            return "a"

        @pipeline_b.step
        def step_for_b() -> str:
            return "b"

        assert STEP_REGISTRY["step_for_a"].step_data.pipeline == "pipeline_a"
        assert STEP_REGISTRY["step_for_b"].step_data.pipeline == "pipeline_b"


# =============================================================================
# Bare @step Backward Compatibility Tests
# =============================================================================


class TestBareStepBackwardCompat:
    """Tests for standalone @step decorator (no pipeline)."""

    def test_bare_step_pipeline_is_none(self):
        """Test that bare @step has pipeline=None."""

        @step
        def standalone_step() -> str:
            return "standalone"

        assert STEP_REGISTRY["standalone_step"].step_data.pipeline is None

    def test_bare_step_with_parens(self):
        """Test that bare @step() has pipeline=None."""

        @step(name="bare_parens")
        def standalone_step() -> str:
            return "standalone"

        assert STEP_REGISTRY["bare_parens"].step_data.pipeline is None


# =============================================================================
# DSL Output Format Tests
# =============================================================================


class TestDslOutputFormat:
    """Tests for the complete DSL output format."""

    def test_dsl_output_structure(self):
        """Test that DSL output has the correct top-level structure."""
        pipeline = Pipeline(name="dsl_test_pipeline", description="Test pipeline")

        @pipeline.step
        def dsl_step_a() -> IntermediateModel:
            return IntermediateModel(processed="a")

        @pipeline.step
        def dsl_step_b(
            input: Annotated[IntermediateModel, step_result(dsl_step_a)],
        ) -> OutputModel:
            return OutputModel(result="b")

        # Build the full DSL output structure
        steps_dict = {
            name: STEP_REGISTRY[name].step_data.model_dump()
            for name in ["dsl_step_a", "dsl_step_b"]
        }
        pipelines_dict = {
            "dsl_test_pipeline": PipelineData(
                name=pipeline.name,
                rid=pipeline.rid,
                description=pipeline.description,
            ).model_dump()
        }

        dsl_output = {
            "steps": steps_dict,
            "pipelines": pipelines_dict,
        }

        # Verify structure
        assert "steps" in dsl_output
        assert "pipelines" in dsl_output

        # Verify steps content
        assert "dsl_step_a" in dsl_output["steps"]
        assert "dsl_step_b" in dsl_output["steps"]
        assert dsl_output["steps"]["dsl_step_a"]["pipeline"] == "dsl_test_pipeline"
        assert dsl_output["steps"]["dsl_step_b"]["pipeline"] == "dsl_test_pipeline"
        assert "depends_on" in dsl_output["steps"]["dsl_step_a"]
        assert "depends_on" in dsl_output["steps"]["dsl_step_b"]

        # Verify pipeline content (metadata only)
        pipeline_output = dsl_output["pipelines"]["dsl_test_pipeline"]
        assert pipeline_output["name"] == "dsl_test_pipeline"
        assert pipeline_output["description"] == "Test pipeline"
        assert "dag" not in pipeline_output
        assert "root_steps" not in pipeline_output
        assert "leaf_steps" not in pipeline_output

    def test_dsl_output_json_serializable(self):
        """Test that the complete DSL output is JSON serializable."""
        pipeline = Pipeline(name="json_pipeline")

        @pipeline.step
        def json_step(data: InputModel) -> OutputModel:
            return OutputModel(result=data.value)

        dsl_output = {
            "steps": {"json_step": STEP_REGISTRY["json_step"].step_data.model_dump()},
            "pipelines": {
                "json_pipeline": PipelineData(
                    name=pipeline.name,
                    rid=pipeline.rid,
                    description=pipeline.description,
                ).model_dump()
            },
        }

        parsed = json.loads(json.dumps(dsl_output))
        assert parsed["pipelines"]["json_pipeline"]["name"] == "json_pipeline"
        assert parsed["steps"]["json_step"]["pipeline"] == "json_pipeline"


# =============================================================================
# Integration Tests
# =============================================================================


class TestPipelineIntegration:
    """Integration tests for the complete pipeline workflow."""

    def test_pipeline_with_step_object_references(self):
        """Test that step_result works with StepFunction objects via @pipeline.step."""
        pipeline = Pipeline(name="ref_pipeline")

        @pipeline.step
        def ref_source() -> IntermediateModel:
            return IntermediateModel(processed="source")

        @pipeline.step
        def ref_target(
            data: Annotated[IntermediateModel, step_result(ref_source)],
        ) -> OutputModel:
            return OutputModel(result=data.processed)

        assert "ref_source" in STEP_REGISTRY["ref_target"].step_data.depends_on
        assert STEP_REGISTRY["ref_target"].step_data.pipeline == "ref_pipeline"

    def test_pipeline_any_variable_name(self):
        """Test that Pipeline can be assigned to any variable name."""
        my_custom_pipeline_name = Pipeline(
            name="custom_named_pipeline",
            description="Pipeline with custom variable name",
        )

        assert "custom_named_pipeline" in PIPELINE_REGISTRY
        assert PIPELINE_REGISTRY["custom_named_pipeline"] is my_custom_pipeline_name
        assert my_custom_pipeline_name.name == "custom_named_pipeline"


# =============================================================================
# Module Discovery Tests
# =============================================================================


class TestModuleDiscovery:
    """Tests for pipeline discovery from modules."""

    @pytest.fixture(autouse=True)
    def clean_example_modules(self):
        """Ensure example modules are re-imported fresh for discovery tests."""
        import sys

        mods_to_remove = [k for k in sys.modules if k.startswith("examples.")]
        for m in mods_to_remove:
            del sys.modules[m]
        yield
        mods_to_remove = [k for k in sys.modules if k.startswith("examples.")]
        for m in mods_to_remove:
            del sys.modules[m]

    def test_discover_pipeline_from_module(self):
        """Test that discover_steps_and_pipelines finds Pipeline instances."""
        steps, pipelines = discover_steps_and_pipelines(["examples.agent_example"])

        # Should find at least one pipeline
        assert len(pipelines) >= 1

        # The agent_example pipeline should be found
        assert "agent_example" in pipelines
        pipeline = pipelines["agent_example"]
        assert pipeline.name == "agent_example"

        # Steps belonging to this pipeline should have pipeline field set
        pipeline_steps = [
            name for name, sf in STEP_REGISTRY.items()
            if sf.step_data.pipeline == "agent_example"
        ]
        assert len(pipeline_steps) > 0

    def test_discover_standalone_steps_module(self):
        """Test that modules without pipelines work (backward compat)."""
        steps, pipelines = discover_steps_and_pipelines(["examples.example"])

        # No pipelines in example.py
        # (example.py only has standalone steps)
        assert len(steps) > 0


# =============================================================================
# Sandbox Definition Tests
# =============================================================================


class TestPipelineStepSandboxDefinition:
    """Tests for sandbox_definition in @pipeline.step decorator."""

    def test_pipeline_step_with_sandbox_definition(self):
        """Test that Pipeline.step() accepts sandbox_definition parameter."""
        from bridge_sdk import SandboxDefinition

        pipeline = Pipeline(name="sandbox_def_pipeline")

        sandbox_def = SandboxDefinition(
            image="python:3.11-slim",
            cpu_request="500m",
            memory_request="1Gi",
        )

        @pipeline.step(
            name="step_with_sandbox_def",
            sandbox_definition=sandbox_def,
        )
        def my_step() -> str:
            return "test"

        assert "step_with_sandbox_def" in STEP_REGISTRY
        step_data = STEP_REGISTRY["step_with_sandbox_def"].step_data
        assert step_data.pipeline == "sandbox_def_pipeline"
        assert step_data.sandbox_definition is not None
        assert step_data.sandbox_definition.image == "python:3.11-slim"
        assert step_data.sandbox_definition.cpu_request == "500m"
        assert step_data.sandbox_definition.memory_request == "1Gi"

    def test_pipeline_step_sandbox_definition_serialization(self):
        """Test that sandbox_definition is serialized correctly for Pipeline steps."""
        import json
        from bridge_sdk import SandboxDefinition

        pipeline = Pipeline(name="serialize_pipeline")

        sandbox_def = SandboxDefinition(
            image="pytorch/pytorch:latest",
            memory_limit="8Gi",
            storage_request="100Gi",
        )

        @pipeline.step(sandbox_definition=sandbox_def)
        def ml_step() -> str:
            return "ML"

        step_data = STEP_REGISTRY["ml_step"].step_data
        dumped = step_data.model_dump(exclude_none=True)

        assert "sandbox_definition" in dumped
        assert dumped["sandbox_definition"]["image"] == "pytorch/pytorch:latest"
        assert dumped["sandbox_definition"]["memory_limit"] == "8Gi"
        assert dumped["sandbox_definition"]["storage_request"] == "100Gi"

        # Verify JSON round-trip
        json_str = json.dumps(dumped)
        parsed = json.loads(json_str)
        assert parsed["sandbox_definition"]["image"] == "pytorch/pytorch:latest"
        assert parsed["sandbox_definition"]["memory_limit"] == "8Gi"
        assert parsed["sandbox_definition"]["storage_request"] == "100Gi"

    def test_pipeline_step_without_sandbox_definition(self):
        """Test that Pipeline steps without sandbox_definition have None value."""
        pipeline = Pipeline(name="no_sandbox_pipeline")

        @pipeline.step
        def plain_step() -> str:
            return "plain"

        step_data = STEP_REGISTRY["plain_step"].step_data
        assert step_data.sandbox_definition is None

        dumped = step_data.model_dump(exclude_none=True)
        assert "sandbox_definition" not in dumped

    def test_pipeline_step_sandbox_def_with_other_options(self):
        """Test sandbox_definition combined with other step options."""
        from bridge_sdk import SandboxDefinition

        pipeline = Pipeline(name="combined_options_pipeline")

        sandbox_def = SandboxDefinition(
            cpu_request="4",
            image="gpu-image:cuda11",
            memory_limit="32Gi",
            memory_request="16Gi",
        )

        @pipeline.step(
            name="combined_step",
            rid="combined-step-rid-123",
            description="A step with many options",
            setup_script="setup.sh",
            metadata={"gpu": True},
            sandbox_definition=sandbox_def,
        )
        def combined_step() -> str:
            return "combined"

        step_data = STEP_REGISTRY["combined_step"].step_data
        assert step_data.name == "combined_step"
        assert step_data.rid == "combined-step-rid-123"
        assert step_data.description == "A step with many options"
        assert step_data.setup_script == "setup.sh"
        assert step_data.metadata == {"gpu": True}
        assert step_data.sandbox_definition is not None
        assert step_data.sandbox_definition.image == "gpu-image:cuda11"
        assert step_data.sandbox_definition.cpu_request == "4"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
