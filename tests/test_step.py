"""Tests for the step decorator functionality."""

import pytest
import importlib
from pathlib import Path
from typing import Annotated
from pydantic import BaseModel

from lib import step, STEP_REGISTRY, StepData, STEP_INPUT, step_result


def test_step_decorator_basic():
    """Test that the step decorator works and registers steps."""
    # Clear registry to start fresh
    STEP_REGISTRY.clear()

    @step(name="test_step")
    def test_function():
        return "test"

    assert "test_step" in STEP_REGISTRY
    # The func stored in StepRecord is the original function, not the wrapper
    step_record = STEP_REGISTRY["test_step"]
    assert callable(step_record.func)
    assert isinstance(step_record.data, StepData)


def test_step_data_file_path_and_line_number():
    """Test that file_path and line_number are captured correctly."""
    STEP_REGISTRY.clear()

    # Define a step function
    @step(name="test_file_location")
    def test_func():
        return "test"

    step_record = STEP_REGISTRY["test_file_location"]
    step_data = step_record.data

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
        execution_env={"image": "test:latest"},
        depends_on=["step1", "step2"],
    )
    def complete_test_func():
        return "complete"

    step_data = STEP_REGISTRY["complete_step"].data

    assert step_data.name == "complete_step"
    assert step_data.setup_script == "setup.sh"
    assert step_data.post_execution_script == "cleanup.sh"
    assert step_data.metadata == {"type": "test"}
    assert step_data.execution_env == {"image": "test:latest"}
    assert step_data.depends_on == ["step1", "step2"]
    assert step_data.file_path is not None
    assert step_data.line_number is not None


def test_examples_file_path_and_line_number():
    """Test file_path and line_number with the actual examples."""
    # Import examples to register their steps
    import examples.example  # noqa: F401

    # Check that steps from example.py have correct file paths
    from examples.example import Steps

    step_1_record = STEP_REGISTRY.get(Steps.STEP_1.value)
    if step_1_record:
        assert step_1_record.data.file_path is not None
        # Should be a relative path
        assert not Path(step_1_record.data.file_path).is_absolute()
        # Should point to example.py relative to repo root
        assert step_1_record.data.file_path == "examples/example.py"
        assert step_1_record.data.line_number is not None
        # Line number should be around line 14-23 (decorator starts at 14, function at 23)
        assert step_1_record.data.line_number >= 10
        assert step_1_record.data.line_number <= 30

    step_2_record = STEP_REGISTRY.get(Steps.STEP_2.value)
    if step_2_record:
        assert step_2_record.data.file_path is not None
        # Should be a relative path
        assert not Path(step_2_record.data.file_path).is_absolute()
        assert step_2_record.data.file_path == "examples/example.py"
        assert step_2_record.data.line_number is not None
        # step_2 decorator starts at 28, function at 37
        assert step_2_record.data.line_number >= 25
        assert step_2_record.data.line_number <= 45


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


def test_parameter_extraction_no_parameters():
    """Test parameter extraction for a step with no parameters."""
    STEP_REGISTRY.clear()

    @step(name="no_params_step")
    def no_params():
        return "test"

    step_data = STEP_REGISTRY["no_params_step"].data
    assert step_data.parameters is not None
    assert len(step_data.parameters) == 0


def test_parameter_extraction_step_input():
    """Test parameter extraction for a step with STEP_INPUT parameter."""
    STEP_REGISTRY.clear()

    @step(name="input_step")
    def input_step(input_data: Annotated[str, STEP_INPUT]):
        return input_data

    step_data = STEP_REGISTRY["input_step"].data
    assert step_data.parameters is not None
    assert len(step_data.parameters) == 1

    param = step_data.parameters[0]
    assert param.name == "input_data"
    assert param.is_step_input is True
    assert param.is_step_result is False
    assert param.step_result_name is None
    assert param.actual_type is str


def test_parameter_extraction_step_input_no_type():
    """Test parameter extraction for STEP_INPUT without type annotation."""
    STEP_REGISTRY.clear()

    @step(name="input_step_no_type")
    def input_step_no_type(input_data: Annotated[None, STEP_INPUT]):
        return input_data

    step_data = STEP_REGISTRY["input_step_no_type"].data
    assert step_data.parameters is not None
    assert len(step_data.parameters) == 1

    param = step_data.parameters[0]
    assert param.name == "input_data"
    assert param.is_step_input is True
    assert param.actual_type is None


def test_parameter_extraction_step_result():
    """Test parameter extraction for a step with step_result parameter."""
    STEP_REGISTRY.clear()

    @step(name="result_step")
    def result_step(prev_result: Annotated[str, step_result("previous_step")]):
        return prev_result

    step_data = STEP_REGISTRY["result_step"].data
    assert step_data.parameters is not None
    assert len(step_data.parameters) == 1

    param = step_data.parameters[0]
    assert param.name == "prev_result"
    assert param.is_step_input is False
    assert param.is_step_result is True
    assert param.step_result_name == "previous_step"
    assert param.actual_type is str


def test_parameter_extraction_step_result_no_type():
    """Test parameter extraction for step_result without type annotation."""
    STEP_REGISTRY.clear()

    @step(name="result_step_no_type")
    def result_step_no_type(prev_result: Annotated[None, step_result("previous_step")]):
        return prev_result

    step_data = STEP_REGISTRY["result_step_no_type"].data
    assert step_data.parameters is not None
    assert len(step_data.parameters) == 1

    param = step_data.parameters[0]
    assert param.name == "prev_result"
    assert param.is_step_result is True
    assert param.step_result_name == "previous_step"
    assert param.actual_type is None


def test_parameter_extraction_both_input_and_result():
    """Test parameter extraction for a step with both STEP_INPUT and step_result."""
    STEP_REGISTRY.clear()

    @step(name="both_params_step")
    def both_params(
        input_data: Annotated[str, STEP_INPUT],
        prev_result: Annotated[str, step_result("previous_step")],
    ):
        return f"{input_data}:{prev_result}"

    step_data = STEP_REGISTRY["both_params_step"].data
    assert step_data.parameters is not None
    assert len(step_data.parameters) == 2

    input_param = step_data.parameters[0]
    assert input_param.name == "input_data"
    assert input_param.is_step_input is True
    assert input_param.is_step_result is False
    assert input_param.actual_type is str

    result_param = step_data.parameters[1]
    assert result_param.name == "prev_result"
    assert result_param.is_step_input is False
    assert result_param.is_step_result is True
    assert result_param.step_result_name == "previous_step"
    assert result_param.actual_type is str


def test_parameter_extraction_regular_parameter():
    """Test parameter extraction for a step with regular (non-annotated) parameters."""
    STEP_REGISTRY.clear()

    @step(name="regular_param_step")
    def regular_param(regular_arg: str):
        return regular_arg

    step_data = STEP_REGISTRY["regular_param_step"].data
    assert step_data.parameters is not None
    assert len(step_data.parameters) == 1

    param = step_data.parameters[0]
    assert param.name == "regular_arg"
    assert param.is_step_input is False
    assert param.is_step_result is False
    assert param.step_result_name is None
    # Regular parameters without annotations won't have actual_type extracted
    assert param.actual_type is None


def test_parameter_extraction_pydantic_model():
    """Test parameter extraction with Pydantic model types."""
    STEP_REGISTRY.clear()

    class InputModel(BaseModel):
        value: str

    class ResultModel(BaseModel):
        data: int

    @step(name="pydantic_step")
    def pydantic_step(
        input_data: Annotated[InputModel, STEP_INPUT],
        prev_result: Annotated[ResultModel, step_result("previous_step")],
    ):
        return input_data.value

    step_data = STEP_REGISTRY["pydantic_step"].data
    assert step_data.parameters is not None
    assert len(step_data.parameters) == 2

    input_param = step_data.parameters[0]
    assert input_param.name == "input_data"
    assert input_param.is_step_input is True
    assert input_param.actual_type == InputModel

    result_param = step_data.parameters[1]
    assert result_param.name == "prev_result"
    assert result_param.is_step_result is True
    assert result_param.actual_type == ResultModel


def test_parameter_extraction_skips_self():
    """Test that 'self' parameter is skipped in parameter extraction."""
    STEP_REGISTRY.clear()

    class StepClass:
        @step(name="method_step")
        def method_step(self, input_data: Annotated[str, STEP_INPUT]):
            return input_data

    step_data = STEP_REGISTRY["method_step"].data
    assert step_data.parameters is not None
    # Should only have input_data, not self
    assert len(step_data.parameters) == 1
    assert step_data.parameters[0].name == "input_data"
    assert "self" not in [p.name for p in step_data.parameters]


def test_parameter_extraction_multiple_step_results():
    """Test parameter extraction with multiple step result parameters."""
    STEP_REGISTRY.clear()

    @step(name="multi_result_step")
    def multi_result(
        result1: Annotated[str, step_result("step1")],
        result2: Annotated[int, step_result("step2")],
        result3: Annotated[bool, step_result("step3")],
    ):
        return f"{result1}:{result2}:{result3}"

    step_data = STEP_REGISTRY["multi_result_step"].data
    assert step_data.parameters is not None
    assert len(step_data.parameters) == 3

    assert step_data.parameters[0].name == "result1"
    assert step_data.parameters[0].step_result_name == "step1"
    assert step_data.parameters[0].actual_type is str

    assert step_data.parameters[1].name == "result2"
    assert step_data.parameters[1].step_result_name == "step2"
    assert step_data.parameters[1].actual_type is int

    assert step_data.parameters[2].name == "result3"
    assert step_data.parameters[2].step_result_name == "step3"
    assert step_data.parameters[2].actual_type is bool


def test_parameter_extraction_examples():
    """Test parameter extraction with actual examples from example.py."""
    # Reload the module to ensure decorators run and register steps
    import examples.example  # noqa: F401

    importlib.reload(examples.example)

    from examples.example import Steps

    # Test step_1 which has only STEP_INPUT
    step_1_data = STEP_REGISTRY[Steps.STEP_1.value].data
    assert step_1_data.parameters is not None
    assert len(step_1_data.parameters) == 1
    assert step_1_data.parameters[0].name == "input_data"
    assert step_1_data.parameters[0].is_step_input is True
    assert step_1_data.parameters[0].actual_type is str

    # Test step_2 which has both STEP_INPUT and step_result
    step_2_data = STEP_REGISTRY[Steps.STEP_2.value].data
    assert step_2_data.parameters is not None
    assert len(step_2_data.parameters) == 2
    assert step_2_data.parameters[0].name == "input_data"
    assert step_2_data.parameters[0].is_step_input is True
    assert step_2_data.parameters[1].name == "step_1_result"
    assert step_2_data.parameters[1].is_step_result is True
    assert step_2_data.parameters[1].step_result_name == Steps.STEP_1.value


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
