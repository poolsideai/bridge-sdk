"""Tests for the step decorator functionality."""

import os
import pytest
import tempfile
from pathlib import Path
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Discriminator

from lib import step, STEP_REGISTRY, StepData, get_dsl_output, step_result


# Test Pydantic models
class SimpleInput(BaseModel):
    value: str


class SimpleOutput(BaseModel):
    result: str


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear the step registry before each test."""
    STEP_REGISTRY.clear()
    yield
    STEP_REGISTRY.clear()


def test_step_decorator_registers_step_with_all_fields():
    """Test that the step decorator registers steps with all StepData fields."""

    @step(
        name="complete_step",
        description="A test step",
        setup_script="setup.sh",
        post_execution_script="cleanup.sh",
        metadata={"type": "test"},
        sandbox_id="test-sandbox",
    )
    def complete_test_func() -> str:
        return "complete"

    assert "complete_step" in STEP_REGISTRY
    step_record = STEP_REGISTRY["complete_step"]

    from lib.step import StepAttributes

    assert isinstance(step_record, StepAttributes)

    step_data = step_record.step_data
    assert isinstance(step_data, StepData)
    assert step_data.name == "complete_step"
    assert step_data.description == "A test step"
    assert step_data.setup_script == "setup.sh"
    assert step_data.post_execution_script == "cleanup.sh"
    assert step_data.metadata == {"type": "test"}
    assert step_data.sandbox_id == "test-sandbox"
    assert step_data.depends_on == []  # No step_result annotations
    assert step_data.file_path == "tests/test_step.py"
    assert step_data.file_line_number is not None
    assert step_data.file_line_number > 0


def test_step_decorator_uses_function_name_when_no_name_provided():
    """Test that step name defaults to function name."""

    @step()
    def my_function_name() -> str:
        return "test"

    assert "my_function_name" in STEP_REGISTRY
    assert STEP_REGISTRY["my_function_name"].step_data.name == "my_function_name"


def test_depends_on_derived_from_annotations():
    """Test that depends_on is automatically derived from step_result annotations."""

    @step(name="upstream_one")
    def upstream_one() -> SimpleOutput:
        return SimpleOutput(result="one")

    @step(name="upstream_two")
    def upstream_two() -> SimpleOutput:
        return SimpleOutput(result="two")

    # Single dependency
    @step(name="single_dep")
    def single_dep(
        upstream: Annotated[SimpleOutput, step_result("upstream_one")],
    ) -> SimpleOutput:
        return upstream

    data = STEP_REGISTRY["single_dep"].step_data
    assert "upstream_one" in data.depends_on
    assert len(data.depends_on) == 1
    assert data.params_from_step_results["upstream"] == "upstream_one"

    # Multiple dependencies
    @step(name="multi_dep")
    def multi_dep(
        first: Annotated[SimpleOutput, step_result("upstream_one")],
        second: Annotated[SimpleOutput, step_result("upstream_two")],
    ) -> SimpleOutput:
        return first

    data = STEP_REGISTRY["multi_dep"].step_data
    assert "upstream_one" in data.depends_on
    assert "upstream_two" in data.depends_on
    assert len(data.depends_on) == 2

    # Mixed annotated and regular parameters
    @step(name="mixed_params")
    def mixed_params(
        regular: str,
        upstream: Annotated[SimpleOutput, step_result("upstream_one")],
        default_param: int = 42,
    ) -> SimpleOutput:
        return upstream

    data = STEP_REGISTRY["mixed_params"].step_data
    assert "upstream_one" in data.depends_on
    assert len(data.depends_on) == 1

    # Duplicate dependencies are deduplicated
    @step(name="duplicate_dep")
    def duplicate_dep(
        first: Annotated[SimpleOutput, step_result("upstream_one")],
        second: Annotated[SimpleOutput, step_result("upstream_one")],
    ) -> SimpleOutput:
        return first

    data = STEP_REGISTRY["duplicate_dep"].step_data
    assert len(data.depends_on) == 1


def test_step_result_with_step_object_references():
    """Test that step_result() works with Step objects and uses override names."""

    # Step without name override
    @step()
    def step_no_override() -> SimpleOutput:
        return SimpleOutput(result="no_override")

    # Step with name override
    @step(name="custom_name")
    def step_with_override() -> SimpleOutput:
        return SimpleOutput(result="override")

    # Reference step without override - should use function name
    @step(name="ref_no_override")
    def ref_no_override(
        dep: Annotated[SimpleOutput, step_result(step_no_override)],
    ) -> SimpleOutput:
        return dep

    data = STEP_REGISTRY["ref_no_override"].step_data
    assert data.params_from_step_results["dep"] == "step_no_override"
    assert "step_no_override" in data.depends_on

    # Reference step with override - should use override name
    @step(name="ref_with_override")
    def ref_with_override(
        dep: Annotated[SimpleOutput, step_result(step_with_override)],
    ) -> SimpleOutput:
        return dep

    data = STEP_REGISTRY["ref_with_override"].step_data
    assert data.params_from_step_results["dep"] == "custom_name"
    assert "custom_name" in data.depends_on
    assert "step_with_override" not in data.depends_on


def test_file_path_resolution_in_sandbox_environment():
    """Test that file_path resolution works when repo is cloned to a temp location."""
    import importlib.util
    import sys

    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir) / "repo"
        repo_root.mkdir()
        (repo_root / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        subdir = repo_root / "examples"
        subdir.mkdir()
        test_module_file = subdir / "sandbox_test_module.py"
        test_module_file.write_text("""from lib import step

@step(name="sandbox_test_step")
def sandbox_test_function():
    return "test"
""")

        old_cwd = os.getcwd()
        try:
            subdir_cwd = repo_root / "some" / "subdirectory"
            subdir_cwd.mkdir(parents=True)
            os.chdir(str(subdir_cwd))

            spec = importlib.util.spec_from_file_location(
                "sandbox_test_module", str(test_module_file)
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules["sandbox_test_module"] = module
            spec.loader.exec_module(module)

            step_data = STEP_REGISTRY["sandbox_test_step"].step_data
            assert step_data.file_path == "examples/sandbox_test_module.py"
            assert not Path(step_data.file_path).is_absolute()
        finally:
            os.chdir(old_cwd)
            if "sandbox_test_module" in sys.modules:
                del sys.modules["sandbox_test_module"]


def test_params_and_return_json_schema():
    """Test that params and return JSON schemas are properly generated."""

    # No parameters
    @step(name="no_params")
    def no_params() -> str:
        return "test"

    data = STEP_REGISTRY["no_params"].step_data
    assert "properties" in data.params_json_schema
    assert len(data.params_json_schema["properties"]) == 0

    # With parameters and defaults
    @step(name="with_params")
    def with_params(x: int, y: str = "default") -> SimpleOutput:
        return SimpleOutput(result=f"{x}:{y}")

    data = STEP_REGISTRY["with_params"].step_data
    assert "x" in data.params_json_schema["properties"]
    assert "y" in data.params_json_schema["properties"]
    assert "x" in data.params_json_schema.get("required", [])
    assert "properties" in data.return_json_schema or "$ref" in data.return_json_schema

    # Complex return type (discriminated union)
    class SuccessResponse(BaseModel):
        status: Literal["success"]
        data: str

    class ErrorResponse(BaseModel):
        status: Literal["error"]
        message: str

    Response = Annotated[
        Union[SuccessResponse, ErrorResponse],
        Discriminator("status"),
    ]

    @step(name="complex_return")
    def complex_return() -> Response:
        return SuccessResponse(status="success", data="test")

    data = STEP_REGISTRY["complex_return"].step_data
    schema = data.return_json_schema
    assert any(k in schema for k in ("type", "anyOf", "oneOf", "$defs"))


def test_get_dsl_output():
    """Test that get_dsl_output returns JSON-serializable data."""
    import json

    @step(name="dsl_test_step")
    def dsl_test_step(input_data: SimpleInput) -> SimpleOutput:
        return SimpleOutput(result=input_data.value)

    dsl_output = get_dsl_output()

    # Should be JSON serializable
    json.dumps(dsl_output)

    assert "dsl_test_step" in dsl_output
    step_data = dsl_output["dsl_test_step"]
    assert "params_json_schema" in step_data
    assert "return_json_schema" in step_data
    assert isinstance(step_data["params_json_schema"], dict)
    assert isinstance(step_data["return_json_schema"], dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
