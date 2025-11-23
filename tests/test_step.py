"""Tests for the step decorator functionality."""

import pytest
from pathlib import Path
from pydantic import BaseModel

from lib import step, STEP_REGISTRY, StepData, StepRecord, get_dsl_output


# Test Pydantic models
class TestInput(BaseModel):
    value: str


class TestOutput(BaseModel):
    result: str


class TestIntInput(BaseModel):
    value: int


class TestBoolInput(BaseModel):
    value: bool


def test_step_decorator_basic():
    """Test that the step decorator works and registers steps."""
    # Clear registry to start fresh
    STEP_REGISTRY.clear()

    @step(name="test_step")
    def test_function():
        return "test"

    assert "test_step" in STEP_REGISTRY
    # STEP_REGISTRY now stores StepRecord objects
    step_record = STEP_REGISTRY["test_step"]
    assert isinstance(step_record, StepRecord)
    step_data = step_record.data
    assert isinstance(step_data, StepData)
    assert step_data.name == "test_step"


def test_step_data_file_path_and_line_number():
    """Test that file_path and line_number are captured correctly."""
    STEP_REGISTRY.clear()

    # Define a step function
    @step(name="test_file_location")
    def test_func():
        return "test"

    step_data = STEP_REGISTRY["test_file_location"].data

    # Verify file_path is set
    assert step_data.file_path is not None
    assert isinstance(step_data.file_path, str)
    # Should be a relative path (not absolute)
    assert not Path(step_data.file_path).is_absolute()
    # Should point to this test file
    assert "test_step.py" in step_data.file_path
    # Should be relative from repo root
    assert step_data.file_path.startswith("tests/")

    # Verify line_number is set
    assert step_data.line_number is not None
    assert isinstance(step_data.line_number, int)
    assert step_data.line_number > 0


def test_step_data_all_fields():
    """Test that all StepData fields are properly set."""
    STEP_REGISTRY.clear()

    @step(
        name="complete_step",
        setup_script="setup.sh",
        post_execution_script="cleanup.sh",
        metadata={"type": "test"},
        sandbox_id="test-sandbox",
        depends_on=["step1", "step2"],
    )
    def complete_test_func():
        return "complete"

    step_data = STEP_REGISTRY["complete_step"].data

    assert step_data.name == "complete_step"
    assert step_data.setup_script == "setup.sh"
    assert step_data.post_execution_script == "cleanup.sh"
    assert step_data.metadata == {"type": "test"}
    assert step_data.sandbox_id == "test-sandbox"
    assert step_data.depends_on_steps == ["step1", "step2"]
    assert step_data.file_path is not None
    assert step_data.line_number is not None


def test_examples_file_path_and_line_number():
    """Test file_path and line_number with the actual examples."""
    # Import examples to register their steps
    import examples.example  # noqa: F401

    # Check that steps from example.py have correct file paths
    # step_1 has no name_override, so it's registered as "step_1"
    step_1_record = STEP_REGISTRY.get("step_1")
    if step_1_record:
        step_1_data = step_1_record.data
        assert step_1_data.file_path is not None
        # Should be a relative path
        assert not Path(step_1_data.file_path).is_absolute()
        # Should point to example.py relative to repo root
        assert step_1_data.file_path == "examples/example.py"
        assert step_1_data.line_number is not None
        # Line number should be around line 18-23 (decorator starts at 18, function at 23)
        assert step_1_data.line_number >= 15
        assert step_1_data.line_number <= 30

    # step_2 has name_override="step_2_override", so it's registered as "step_2_override"
    step_2_record = STEP_REGISTRY.get("step_2_override")
    if step_2_record:
        step_2_data = step_2_record.data
        assert step_2_data.file_path is not None
        # Should be a relative path
        assert not Path(step_2_data.file_path).is_absolute()
        assert step_2_data.file_path == "examples/example.py"
        assert step_2_data.line_number is not None
        # step_2 decorator starts at 36, function at 44
        assert step_2_data.line_number >= 30
        assert step_2_data.line_number <= 50


def test_multiple_steps_different_locations():
    """Test that different steps have different line numbers."""
    STEP_REGISTRY.clear()

    @step(name="step_a")
    def step_a():
        return "a"

    # Add some spacing
    _ = None
    _ = None
    _ = None

    @step(name="step_b")
    def step_b():
        return "b"

    step_a_data = STEP_REGISTRY["step_a"].data
    step_b_data = STEP_REGISTRY["step_b"].data

    # Both should have file paths
    assert step_a_data.file_path is not None
    assert step_b_data.file_path is not None

    # Both should have line numbers
    assert step_a_data.line_number is not None
    assert step_b_data.line_number is not None

    # Line numbers should be different
    assert step_a_data.line_number != step_b_data.line_number
    # step_b should be defined after step_a
    assert step_b_data.line_number > step_a_data.line_number


def test_step_without_name():
    """Test that step works even without a name (though it may not register properly)."""
    STEP_REGISTRY.clear()

    @step()
    def unnamed_step():
        return "unnamed"

    # The step should still be callable
    result = unnamed_step()
    assert result == "unnamed"

    # Note: Without a name, it won't be in the registry
    # This tests that the decorator doesn't crash


def test_params_json_schema_no_parameters():
    """Test params_json_schema for a step with no parameters."""
    STEP_REGISTRY.clear()

    @step(name="no_params_step")
    def no_params():
        return "test"

    step_data = STEP_REGISTRY["no_params_step"].data
    assert step_data.params_json_schema is not None
    assert isinstance(step_data.params_json_schema, dict)
    # Should have properties (even if empty)
    assert "properties" in step_data.params_json_schema
    assert len(step_data.params_json_schema["properties"]) == 0


def test_params_json_schema_with_parameters():
    """Test params_json_schema for a step with parameters."""
    STEP_REGISTRY.clear()

    @step(name="params_step")
    def params_step(x: int, y: str = "default"):
        return f"{x}:{y}"

    step_data = STEP_REGISTRY["params_step"].data
    assert step_data.params_json_schema is not None
    assert isinstance(step_data.params_json_schema, dict)
    assert "properties" in step_data.params_json_schema
    # Should have x and y in properties
    assert "x" in step_data.params_json_schema["properties"]
    assert "y" in step_data.params_json_schema["properties"]
    # x should be required, y should have a default
    assert "x" in step_data.params_json_schema.get("required", [])


def test_return_json_schema():
    """Test return_json_schema for a step with return type."""
    STEP_REGISTRY.clear()

    @step(name="return_step")
    def return_step() -> TestOutput:
        return TestOutput(result="test")

    step_data = STEP_REGISTRY["return_step"].data
    assert step_data.return_json_schema is not None
    assert isinstance(step_data.return_json_schema, dict)
    # Should have schema information for TestOutput
    # JSON schema can have "type", "properties", or "$ref" for references
    assert (
        "type" in step_data.return_json_schema
        or "properties" in step_data.return_json_schema
        or "$ref" in step_data.return_json_schema
    )


def test_return_json_schema_no_return_type():
    """Test return_json_schema for a step without return type annotation."""
    STEP_REGISTRY.clear()

    @step(name="no_return_step")
    def no_return_step():
        return "test"

    step_data = STEP_REGISTRY["no_return_step"].data
    # Should still have return_json_schema (may be empty dict or Any schema)
    assert step_data.return_json_schema is not None
    assert isinstance(step_data.return_json_schema, dict)


def test_params_json_schema_with_pydantic_input():
    """Test params_json_schema with Pydantic model input."""
    STEP_REGISTRY.clear()

    @step(name="pydantic_input_step")
    def pydantic_input_step(input_data: TestInput) -> TestOutput:
        return TestOutput(result=input_data.value)

    step_data = STEP_REGISTRY["pydantic_input_step"].data
    assert step_data.params_json_schema is not None
    assert "properties" in step_data.params_json_schema
    assert "input_data" in step_data.params_json_schema["properties"]


def test_get_dsl_output_json_serializable():
    """Test that get_dsl_output returns JSON-serializable data."""
    STEP_REGISTRY.clear()

    @step(name="test_json_step")
    def test_step(input_data: TestInput) -> TestOutput:
        return TestOutput(result=input_data.value)

    # Get DSL output
    dsl_output = get_dsl_output()

    # Verify it's JSON serializable (this should not raise an exception)
    import json

    json.dumps(dsl_output, indent=2)

    # Verify the structure
    assert "test_json_step" in dsl_output
    step_data = dsl_output["test_json_step"]
    assert "params_json_schema" in step_data
    assert "return_json_schema" in step_data


def test_get_dsl_output_with_pydantic_model():
    """Test that get_dsl_output handles Pydantic models correctly."""
    STEP_REGISTRY.clear()

    class TestInput(BaseModel):
        value: str

    class TestOutput(BaseModel):
        result: str

    @step(name="test_pydantic_step")
    def test_step(input_data: TestInput) -> TestOutput:
        return TestOutput(result=input_data.value)

    # Get DSL output
    dsl_output = get_dsl_output()

    # Verify it's JSON serializable (this should not raise an exception)
    import json

    json.dumps(dsl_output, indent=2)

    # Verify Pydantic model is properly serialized
    step_data = dsl_output["test_pydantic_step"]
    assert "params_json_schema" in step_data
    assert "return_json_schema" in step_data
    # Check that schemas contain proper structure
    assert isinstance(step_data["params_json_schema"], dict)
    assert isinstance(step_data["return_json_schema"], dict)


def test_params_from_step_results():
    """Test that params_from_step_results is properly set."""
    STEP_REGISTRY.clear()
    from typing import Annotated
    from lib import step_result

    @step(name="step_with_deps")
    def step_with_deps(
        prev_result: Annotated[TestOutput, step_result("previous_step")],
    ) -> TestOutput:
        return prev_result

    step_data = STEP_REGISTRY["step_with_deps"].data
    assert step_data.params_from_step_results is not None
    assert isinstance(step_data.params_from_step_results, dict)
    assert step_data.params_from_step_results["prev_result"] == "previous_step"


def test_optional_return_type():
    """Test return_json_schema with Optional return type."""
    STEP_REGISTRY.clear()
    from typing import Optional

    @step(name="optional_return_step")
    def optional_return_step() -> Optional[TestOutput]:
        return TestOutput(result="test")

    step_data = STEP_REGISTRY["optional_return_step"].data
    assert step_data.return_json_schema is not None
    assert isinstance(step_data.return_json_schema, dict)


def test_union_return_type():
    """Test return_json_schema with Union return type."""
    STEP_REGISTRY.clear()
    from typing import Union

    class Model1(BaseModel):
        value: str

    class Model2(BaseModel):
        value: int

    @step(name="union_return_step")
    def union_return_step() -> Union[Model1, Model2]:
        return Model1(value="test")

    step_data = STEP_REGISTRY["union_return_step"].data
    assert step_data.return_json_schema is not None
    assert isinstance(step_data.return_json_schema, dict)


def test_discriminated_union_return_type():
    """Test return_json_schema with a Pydantic discriminated union return type."""
    STEP_REGISTRY.clear()
    from typing import Annotated, Literal, Union
    from pydantic import Discriminator

    class SuccessResponse(BaseModel):
        status: Literal["success"]
        data: str
        code: int = 200

    class ErrorResponse(BaseModel):
        status: Literal["error"]
        message: str
        code: int = 400

    # Create a discriminated union using Annotated with Discriminator
    Response = Annotated[
        Union[SuccessResponse, ErrorResponse],
        Discriminator("status"),
    ]

    @step(name="discriminated_union_step")
    def discriminated_union_step() -> Response:
        return SuccessResponse(status="success", data="test data")

    step_data = STEP_REGISTRY["discriminated_union_step"].data
    assert step_data.return_json_schema is not None
    assert isinstance(step_data.return_json_schema, dict)

    # Verify the schema contains information about the discriminated union
    # The schema should have either "anyOf", "oneOf", or discriminator information
    schema = step_data.return_json_schema
    # Check that it's a valid JSON schema structure
    assert (
        "type" in schema or "anyOf" in schema or "oneOf" in schema or "$defs" in schema
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
