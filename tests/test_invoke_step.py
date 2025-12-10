"""Tests for step.on_invoke_step with various input types and sync/async functions."""

import asyncio
import json
import pytest
from typing import Annotated, Optional, List, Dict, Any
from pydantic import BaseModel

from bridge_sdk import step, STEP_REGISTRY, step_result
from bridge_sdk.exceptions import StepError


class SimpleInput(BaseModel):
    value: str


class SimpleOutput(BaseModel):
    result: str


class NestedInput(BaseModel):
    outer: str
    inner: SimpleInput


class ComplexInput(BaseModel):
    name: str
    age: int
    active: bool
    tags: List[str]
    metadata: Dict[str, Any]
    nested: NestedInput


class OptionalInput(BaseModel):
    required: str
    optional: Optional[str] = None
    default_val: int = 42


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear the step registry before each test."""
    STEP_REGISTRY.clear()
    yield
    STEP_REGISTRY.clear()


# ========== Sync Step Tests ==========


def test_sync_step_no_parameters():
    """Test sync step with no parameters."""

    @step(name="sync_no_params")
    def sync_no_params() -> str:
        return "success"

    result_json = asyncio.run(
        STEP_REGISTRY["sync_no_params"].on_invoke_step("{}", "{}")
    )
    assert json.loads(result_json) == "success"


def test_sync_step_with_complex_input():
    """Test sync step with complex nested Pydantic input."""

    @step(name="sync_complex")
    def sync_complex(input_data: ComplexInput) -> SimpleOutput:
        return SimpleOutput(
            result=f"{input_data.name}_{input_data.age}_{len(input_data.tags)}"
        )

    result_json = asyncio.run(
        STEP_REGISTRY["sync_complex"].on_invoke_step(
            '{"input_data": {"name": "John", "age": 30, "active": true, '
            '"tags": ["a", "b"], "metadata": {"key": "val"}, '
            '"nested": {"outer": "out", "inner": {"value": "in"}}}}',
            "{}",
        )
    )
    result = SimpleOutput.model_validate_json(result_json)
    assert result.result == "John_30_2"


def test_sync_step_multiple_params_with_defaults():
    """Test sync step with multiple parameters and defaults."""

    @step(name="sync_defaults")
    def sync_defaults(
        required: str, optional: str = "default", number: int = 10
    ) -> SimpleOutput:
        return SimpleOutput(result=f"{required}_{optional}_{number}")

    # With all parameters
    result_json = asyncio.run(
        STEP_REGISTRY["sync_defaults"].on_invoke_step(
            '{"required": "req", "optional": "custom", "number": 20}', "{}"
        )
    )
    assert SimpleOutput.model_validate_json(result_json).result == "req_custom_20"

    # With defaults
    result_json = asyncio.run(
        STEP_REGISTRY["sync_defaults"].on_invoke_step('{"required": "req"}', "{}")
    )
    assert SimpleOutput.model_validate_json(result_json).result == "req_default_10"


def test_sync_step_with_step_results():
    """Test sync step that uses results from previous steps."""

    @step(name="step_a")
    def step_a() -> SimpleOutput:
        return SimpleOutput(result="from_a")

    @step(name="step_b")
    def step_b(
        input_data: SimpleInput,
        step_a_result: Annotated[SimpleOutput, step_result("step_a")],
    ) -> SimpleOutput:
        return SimpleOutput(result=f"{input_data.value}_{step_a_result.result}")

    result_json = asyncio.run(
        STEP_REGISTRY["step_b"].on_invoke_step(
            '{"input_data": {"value": "test"}}',
            '{"step_a": {"result": "from_a"}}',
        )
    )
    assert SimpleOutput.model_validate_json(result_json).result == "test_from_a"


# ========== Async Step Tests ==========


@pytest.mark.asyncio
async def test_async_step_no_parameters():
    """Test async step with no parameters."""

    @step(name="async_no_params")
    async def async_no_params() -> str:
        return "async_success"

    result_json = await STEP_REGISTRY["async_no_params"].on_invoke_step("{}", "{}")
    assert json.loads(result_json) == "async_success"


@pytest.mark.asyncio
async def test_async_step_with_complex_input():
    """Test async step with complex nested input."""

    @step(name="async_complex")
    async def async_complex(input_data: ComplexInput) -> SimpleOutput:
        return SimpleOutput(result=f"async_{input_data.name}_{input_data.age}")

    result_json = await STEP_REGISTRY["async_complex"].on_invoke_step(
        '{"input_data": {"name": "Jane", "age": 25, "active": true, '
        '"tags": ["x"], "metadata": {}, "nested": {"outer": "o", "inner": {"value": "i"}}}}',
        "{}",
    )
    assert SimpleOutput.model_validate_json(result_json).result == "async_Jane_25"


@pytest.mark.asyncio
async def test_async_step_with_await_operations():
    """Test async step that performs async operations."""

    @step(name="async_operations")
    async def async_operations(input_data: SimpleInput) -> SimpleOutput:
        await asyncio.sleep(0.001)
        return SimpleOutput(result=f"delayed_{input_data.value}")

    result_json = await STEP_REGISTRY["async_operations"].on_invoke_step(
        '{"input_data": {"value": "test"}}', "{}"
    )
    assert SimpleOutput.model_validate_json(result_json).result == "delayed_test"


@pytest.mark.asyncio
async def test_async_step_with_step_results():
    """Test async step that uses results from previous steps."""

    @step(name="async_step_a")
    async def async_step_a() -> SimpleOutput:
        return SimpleOutput(result="async_from_a")

    @step(name="async_step_b")
    async def async_step_b(
        input_data: SimpleInput,
        async_step_a_result: Annotated[SimpleOutput, step_result("async_step_a")],
    ) -> SimpleOutput:
        return SimpleOutput(
            result=f"async_{input_data.value}_{async_step_a_result.result}"
        )

    result_json = await STEP_REGISTRY["async_step_b"].on_invoke_step(
        '{"input_data": {"value": "test"}}',
        '{"async_step_a": {"result": "async_from_a"}}',
    )
    assert (
        SimpleOutput.model_validate_json(result_json).result
        == "async_test_async_from_a"
    )


# ========== Error Cases ==========


def test_error_invalid_json_input():
    """Test that invalid JSON input raises an error."""

    @step(name="error_step")
    def error_step(input_data: SimpleInput) -> SimpleOutput:
        return SimpleOutput(result="ok")

    with pytest.raises(StepError, match="Invalid JSON input"):
        asyncio.run(STEP_REGISTRY["error_step"].on_invoke_step("not json", "{}"))


def test_error_missing_required_field():
    """Test that missing required fields raise validation errors."""

    @step(name="error_step")
    def error_step(input_data: SimpleInput) -> SimpleOutput:
        return SimpleOutput(result="ok")

    with pytest.raises(StepError, match="Invalid JSON input"):
        asyncio.run(
            STEP_REGISTRY["error_step"].on_invoke_step('{"input_data": {}}', "{}")
        )


def test_error_invalid_field_type():
    """Test that invalid field types raise validation errors."""

    @step(name="error_step")
    def error_step(input_data: SimpleInput) -> SimpleOutput:
        return SimpleOutput(result="ok")

    with pytest.raises(StepError, match="Invalid JSON input"):
        asyncio.run(
            STEP_REGISTRY["error_step"].on_invoke_step(
                '{"input_data": {"value": 123}}', "{}"
            )
        )


# ========== Edge Cases ==========


def test_empty_input():
    """Test step with empty input."""

    @step(name="empty_input")
    def empty_input() -> str:
        return "empty_ok"

    assert (
        json.loads(asyncio.run(STEP_REGISTRY["empty_input"].on_invoke_step("{}", "{}")))
        == "empty_ok"
    )
    assert (
        json.loads(asyncio.run(STEP_REGISTRY["empty_input"].on_invoke_step("", "")))
        == "empty_ok"
    )


def test_edge_cases():
    """Test step with edge cases: large input, special chars, unicode."""

    @step(name="edge_cases")
    def edge_cases(input_data: SimpleInput) -> SimpleOutput:
        return SimpleOutput(result=f"len_{len(input_data.value)}")

    # Large input
    large_value = "x" * 10000
    result_json = asyncio.run(
        STEP_REGISTRY["edge_cases"].on_invoke_step(
            f'{{"input_data": {{"value": "{large_value}"}}}}', "{}"
        )
    )
    assert SimpleOutput.model_validate_json(result_json).result == "len_10000"

    # Special characters and unicode
    special_value = 'test "quotes" 测试 🎉'
    input_json = json.dumps({"input_data": {"value": special_value}})
    result_json = asyncio.run(
        STEP_REGISTRY["edge_cases"].on_invoke_step(input_json, "{}")
    )
    assert (
        SimpleOutput.model_validate_json(result_json).result
        == f"len_{len(special_value)}"
    )


def test_optional_fields_with_none():
    """Test that None values work in optional fields."""

    @step(name="optional_step")
    def optional_step(input_data: OptionalInput) -> SimpleOutput:
        return SimpleOutput(
            result=f"{input_data.required}_{input_data.optional is None}_{input_data.default_val}"
        )

    result_json = asyncio.run(
        STEP_REGISTRY["optional_step"].on_invoke_step(
            '{"input_data": {"required": "req", "optional": null}}', "{}"
        )
    )
    assert SimpleOutput.model_validate_json(result_json).result == "req_True_42"


# ========== Direct Function Invocation Tests ==========


def test_direct_invocation_sync():
    """Test that decorated step functions can be called directly."""

    @step(name="direct_sync")
    def direct_sync(input_data: SimpleInput) -> SimpleOutput:
        return SimpleOutput(result=f"direct_{input_data.value}")

    assert "direct_sync" in STEP_REGISTRY
    result = direct_sync(SimpleInput(value="test"))
    assert result.result == "direct_test"

    @step(name="direct_multi")
    def direct_multi(first: str, second: int, third: bool = True) -> SimpleOutput:
        return SimpleOutput(result=f"{first}_{second}_{third}")

    assert direct_multi("hello", 42, False).result == "hello_42_False"
    assert direct_multi(first="world", second=100).result == "world_100_True"


@pytest.mark.asyncio
async def test_direct_invocation_async():
    """Test that decorated async step functions can be called directly."""

    @step(name="direct_async")
    async def direct_async(input_data: SimpleInput) -> SimpleOutput:
        return SimpleOutput(result=f"direct_async_{input_data.value}")

    assert "direct_async" in STEP_REGISTRY
    result = await direct_async(SimpleInput(value="test"))
    assert result.result == "direct_async_test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
