"""Tests for the step decorator functionality."""

import pytest
from pathlib import Path
from typing import Annotated
from pydantic import BaseModel

from lib import step, STEP_REGISTRY, StepData, get_dsl_output, step_result


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
    # STEP_REGISTRY now stores Step objects
    step_record = STEP_REGISTRY["test_step"]
    from lib.step import Step

    assert isinstance(step_record, Step)
    step_data = step_record.step_data
    assert isinstance(step_data, StepData)
    assert step_data.name == "test_step"


def test_step_data_file_path_and_line_number():
    """Test that file_path and line_number are captured correctly."""
    STEP_REGISTRY.clear()

    # Define a step function
    @step(name="test_file_location")
    def test_func():
        return "test"

    step_record = STEP_REGISTRY["test_file_location"]
    step_data = step_record.step_data

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

    step_record = STEP_REGISTRY["complete_step"]
    step_data = step_record.step_data

    assert step_data.name == "complete_step"
    assert step_data.setup_script == "setup.sh"
    assert step_data.post_execution_script == "cleanup.sh"
    assert step_data.metadata == {"type": "test"}
    assert step_data.sandbox_id == "test-sandbox"
    assert step_data.depends_on == ["step1", "step2"]
    assert step_data.file_path is not None
    assert step_data.line_number is not None


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

    step_a_data = STEP_REGISTRY["step_a"].step_data
    step_b_data = STEP_REGISTRY["step_b"].step_data

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


def test_params_json_schema_no_parameters():
    """Test params_json_schema for a step with no parameters."""
    STEP_REGISTRY.clear()

    @step(name="no_params_step")
    def no_params():
        return "test"

    step_data = STEP_REGISTRY["no_params_step"].step_data
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

    step_data = STEP_REGISTRY["params_step"].step_data
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

    step_data = STEP_REGISTRY["return_step"].step_data
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

    step_data = STEP_REGISTRY["no_return_step"].step_data
    # Should still have return_json_schema (may be empty dict or Any schema)
    assert step_data.return_json_schema is not None
    assert isinstance(step_data.return_json_schema, dict)


def test_params_json_schema_with_pydantic_input():
    """Test params_json_schema with Pydantic model input."""
    STEP_REGISTRY.clear()

    @step(name="pydantic_input_step")
    def pydantic_input_step(input_data: TestInput) -> TestOutput:
        return TestOutput(result=input_data.value)

    step_data = STEP_REGISTRY["pydantic_input_step"].step_data
    assert step_data.params_json_schema is not None
    assert "properties" in step_data.params_json_schema
    assert "input_data" in step_data.params_json_schema["properties"]


def test_get_dsl_output():
    """Test that get_dsl_output returns JSON-serializable data with proper schemas."""
    STEP_REGISTRY.clear()

    @step(name="test_dsl_step")
    def test_step(input_data: TestInput) -> TestOutput:
        return TestOutput(result=input_data.value)

    # Get DSL output
    dsl_output = get_dsl_output()

    # Verify it's JSON serializable
    import json

    json.dumps(dsl_output, indent=2)

    # Verify the structure
    assert "test_dsl_step" in dsl_output
    step_data = dsl_output["test_dsl_step"]
    assert "params_json_schema" in step_data
    assert "return_json_schema" in step_data
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

    step_data = STEP_REGISTRY["step_with_deps"].step_data
    assert step_data.params_from_step_results is not None
    assert isinstance(step_data.params_from_step_results, dict)
    assert step_data.params_from_step_results["prev_result"] == "previous_step"


def test_complex_return_types():
    """Test return_json_schema with complex return types (discriminated union)."""
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

    # Test discriminated union
    Response = Annotated[
        Union[SuccessResponse, ErrorResponse],
        Discriminator("status"),
    ]

    @step(name="complex_return_step")
    def complex_return_step() -> Response:
        return SuccessResponse(status="success", data="test data")

    step_data = STEP_REGISTRY["complex_return_step"].step_data
    assert step_data.return_json_schema is not None
    assert isinstance(step_data.return_json_schema, dict)
    schema = step_data.return_json_schema
    assert (
        "type" in schema or "anyOf" in schema or "oneOf" in schema or "$defs" in schema
    )


# ========== Step Object References in depends_on Tests ==========


def test_depends_on_with_step_objects():
    """Test that depends_on can accept Step objects, strings, and mixed combinations."""
    STEP_REGISTRY.clear()

    @step(name="step_a")
    def step_a() -> TestOutput:
        return TestOutput(result="from_a")

    @step(name="step_b")
    def step_b() -> TestOutput:
        return TestOutput(result="from_b")

    # Test with Step object
    @step(name="step_c", depends_on=[step_a])
    def step_c(
        input_data: TestInput,
        step_a_result: Annotated[TestOutput, step_result("step_a")],
    ) -> TestOutput:
        return TestOutput(result=f"{input_data.value}_{step_a_result.result}")

    # Test with mixed Step objects and strings
    @step(name="step_d", depends_on=[step_b, "step_a"])
    def step_d(
        input_data: TestInput,
        step_b_result: Annotated[TestOutput, step_result("step_b")],
        step_a_result: Annotated[TestOutput, step_result("step_a")],
    ) -> TestOutput:
        return TestOutput(
            result=f"{input_data.value}_{step_b_result.result}_{step_a_result.result}"
        )

    # Test with custom name override
    @step(name="custom_name")
    def step_with_custom_name() -> TestOutput:
        return TestOutput(result="custom")

    @step(name="step_e", depends_on=[step_with_custom_name])
    def step_e(
        input_data: TestInput,
        custom_result: Annotated[TestOutput, step_result(step_with_custom_name)],
    ) -> TestOutput:
        return TestOutput(result=f"{input_data.value}_{custom_result.result}")

    # Verify dependencies
    step_c_data = STEP_REGISTRY["step_c"].step_data
    assert "step_a" in step_c_data.depends_on

    step_d_data = STEP_REGISTRY["step_d"].step_data
    assert "step_b" in step_d_data.depends_on
    assert "step_a" in step_d_data.depends_on

    step_e_data = STEP_REGISTRY["step_e"].step_data
    assert "custom_name" in step_e_data.depends_on
    assert "step_with_custom_name" not in step_e_data.depends_on
    assert step_e_data.params_from_step_results["custom_result"] == "custom_name"

    # Test empty list
    @step(name="step_f", depends_on=[])
    def step_f() -> TestOutput:
        return TestOutput(result="standalone")

    step_f_data = STEP_REGISTRY["step_f"].step_data
    assert step_f_data.depends_on == []


# ========== Step Object References in step_result() Tests ==========


def test_step_result_with_step_objects():
    """Test that step_result() works with Step objects, strings, and name overrides."""
    STEP_REGISTRY.clear()

    # Step without name override - should use function name
    @step()
    def step_no_override() -> TestOutput:
        return TestOutput(result="from_a")

    @step(name="step_b")
    def step_b(
        input_data: TestInput,
        step_a_result: Annotated[TestOutput, step_result(step_no_override)],
    ) -> TestOutput:
        return TestOutput(result=f"{input_data.value}_{step_a_result.result}")

    # Verify uses function name when no override
    step_b_data = STEP_REGISTRY["step_b"].step_data
    assert step_b_data.params_from_step_results["step_a_result"] == "step_no_override"

    # Step with name override
    @step(name="custom_step_name")
    def step_with_override() -> TestOutput:
        return TestOutput(result="from_c")

    @step(name="step_d")
    def step_d(
        input_data: TestInput,
        step_c_result: Annotated[TestOutput, step_result(step_with_override)],
    ) -> TestOutput:
        return TestOutput(result=f"{input_data.value}_{step_c_result.result}")

    # Verify uses override name, not function name
    step_d_data = STEP_REGISTRY["step_d"].step_data
    assert step_d_data.params_from_step_results["step_c_result"] == "custom_step_name"
    assert step_d_data.params_from_step_results["step_c_result"] != "step_with_override"

    # Test backward compatibility with strings
    @step(name="step_e")
    def step_e() -> TestOutput:
        return TestOutput(result="from_e")

    @step(name="step_f")
    def step_f(
        input_data: TestInput,
        step_e_result: Annotated[TestOutput, step_result("step_e")],
    ) -> TestOutput:
        return TestOutput(result=f"{input_data.value}_{step_e_result.result}")

    step_f_data = STEP_REGISTRY["step_f"].step_data
    assert step_f_data.params_from_step_results["step_e_result"] == "step_e"

    # Test multiple step results and mixed Step objects/strings
    @step(name="step_g")
    def step_g() -> TestOutput:
        return TestOutput(result="from_g")

    @step(name="step_h")
    def step_h(
        input_data: TestInput,
        step_g_result: Annotated[TestOutput, step_result(step_g)],
        external_result: Annotated[TestOutput, step_result("external_step")],
    ) -> TestOutput:
        return TestOutput(
            result=f"{input_data.value}_{step_g_result.result}_{external_result.result}"
        )

    step_h_data = STEP_REGISTRY["step_h"].step_data
    assert step_h_data.params_from_step_results["step_g_result"] == "step_g"
    assert step_h_data.params_from_step_results["external_result"] == "external_step"

    # Test that depends_on and step_result both use step's actual name
    @step(name="custom_name")
    def step_custom() -> TestOutput:
        return TestOutput(result="custom")

    @step(name="step_i", depends_on=[step_custom])
    def step_i(
        input_data: TestInput,
        custom_result: Annotated[TestOutput, step_result(step_custom)],
    ) -> TestOutput:
        return TestOutput(result=f"{input_data.value}_{custom_result.result}")

    step_i_data = STEP_REGISTRY["step_i"].step_data
    assert "custom_name" in step_i_data.depends_on
    assert "step_custom" not in step_i_data.depends_on
    assert step_i_data.params_from_step_results["custom_result"] == "custom_name"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
