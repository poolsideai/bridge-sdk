"""Tests for step.on_invoke_step with various input types and sync/async functions."""

import asyncio
import pytest
from typing import Annotated, Optional, Union, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime, date
from enum import Enum

from lib import step, STEP_REGISTRY, step_result
from lib.exceptions import StepError


# Test Pydantic models for various scenarios
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
    optional_with_default: Optional[int] = 42


class UnionInput(BaseModel):
    value: Union[str, int]


class EnumInput(BaseModel):
    class Status(str, Enum):
        PENDING = "pending"
        ACTIVE = "active"
        INACTIVE = "inactive"

    status: Status


class DateTimeInput(BaseModel):
    timestamp: datetime
    date_only: date


class ListInput(BaseModel):
    items: List[str]
    numbers: List[int]


class DictInput(BaseModel):
    mapping: Dict[str, int]
    nested: Dict[str, Dict[str, str]]


class FieldConstraintsInput(BaseModel):
    positive_int: int = Field(gt=0)
    non_empty_str: str = Field(min_length=1)
    bounded_int: int = Field(ge=1, le=100)


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

    step_obj = STEP_REGISTRY["sync_no_params"]
    result = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    assert result == "success"


def test_sync_step_simple_string_input():
    """Test sync step with simple string input."""

    @step(name="sync_string")
    def sync_string(input_data: SimpleInput) -> SimpleOutput:
        return SimpleOutput(result=f"processed_{input_data.value}")

    step_obj = STEP_REGISTRY["sync_string"]
    result = asyncio.run(
        step_obj.on_invoke_step('{"input_data": {"value": "test"}}', "{}")
    )
    assert result.result == "processed_test"


def test_sync_step_complex_types():
    """Test sync step with various Pydantic types (nested, optional, union, collections)."""

    @step(name="sync_complex")
    def sync_complex(input_data: ComplexInput) -> SimpleOutput:
        return SimpleOutput(
            result=f"{input_data.name}_{input_data.age}_{len(input_data.tags)}"
        )

    step_obj = STEP_REGISTRY["sync_complex"]
    result = asyncio.run(
        step_obj.on_invoke_step(
            '{"input_data": {"name": "John", "age": 30, "active": true, '
            '"tags": ["tag1", "tag2"], "metadata": {"key": "value"}, '
            '"nested": {"outer": "out", "inner": {"value": "in"}}}}',
            "{}",
        )
    )
    assert result.result == "John_30_2"

    # Test optional fields
    @step(name="sync_optional")
    def sync_optional(input_data: OptionalInput) -> SimpleOutput:
        return SimpleOutput(
            result=f"{input_data.required}_{input_data.optional}_{input_data.optional_with_default}"
        )

    step_obj = STEP_REGISTRY["sync_optional"]
    result = asyncio.run(
        step_obj.on_invoke_step('{"input_data": {"required": "req"}}', "{}")
    )
    assert result.result == "req_None_42"

    # Test union types
    @step(name="sync_union")
    def sync_union(input_data: UnionInput) -> SimpleOutput:
        return SimpleOutput(result=f"value_{input_data.value}")

    step_obj = STEP_REGISTRY["sync_union"]
    result = asyncio.run(step_obj.on_invoke_step('{"input_data": {"value": 42}}', "{}"))
    assert result.result == "value_42"


def test_sync_step_multiple_parameters():
    """Test sync step with multiple parameters."""

    class MultiInput(BaseModel):
        first: str
        second: int
        third: bool

    @step(name="sync_multi")
    def sync_multi(
        first_param: str, second_param: int, third_param: bool
    ) -> SimpleOutput:
        return SimpleOutput(result=f"{first_param}_{second_param}_{third_param}")

    step_obj = STEP_REGISTRY["sync_multi"]
    result = asyncio.run(
        step_obj.on_invoke_step(
            '{"first_param": "hello", "second_param": 42, "third_param": true}',
            "{}",
        )
    )
    assert result.result == "hello_42_True"


def test_sync_step_with_defaults():
    """Test sync step with default parameter values."""

    @step(name="sync_defaults")
    def sync_defaults(
        required: str, optional: str = "default", number: int = 10
    ) -> SimpleOutput:
        return SimpleOutput(result=f"{required}_{optional}_{number}")

    step_obj = STEP_REGISTRY["sync_defaults"]
    # Test with all parameters
    result = asyncio.run(
        step_obj.on_invoke_step(
            '{"required": "req", "optional": "custom", "number": 20}', "{}"
        )
    )
    assert result.result == "req_custom_20"

    # Test with defaults
    result = asyncio.run(step_obj.on_invoke_step('{"required": "req"}', "{}"))
    assert result.result == "req_default_10"


def test_sync_step_with_step_results():
    """Test sync step that uses results from previous steps."""

    @step(name="step_a")
    def step_a() -> SimpleOutput:
        return SimpleOutput(result="from_a")

    @step(name="step_b", depends_on=["step_a"])
    def step_b(
        input_data: SimpleInput,
        step_a_result: Annotated[SimpleOutput, step_result("step_a")],
    ) -> SimpleOutput:
        return SimpleOutput(result=f"{input_data.value}_{step_a_result.result}")

    step_obj = STEP_REGISTRY["step_b"]
    result = asyncio.run(
        step_obj.on_invoke_step(
            '{"input_data": {"value": "test"}}',
            '{"step_a": {"result": "from_a"}}',
        )
    )
    assert result.result == "test_from_a"


# ========== Async Step Tests ==========


@pytest.mark.asyncio
async def test_async_step_no_parameters():
    """Test async step with no parameters."""

    @step(name="async_no_params")
    async def async_no_params() -> str:
        return "async_success"

    step_obj = STEP_REGISTRY["async_no_params"]
    result = await step_obj.on_invoke_step("{}", "{}")
    assert result == "async_success"


@pytest.mark.asyncio
async def test_async_step_simple_input():
    """Test async step with simple input."""

    @step(name="async_string")
    async def async_string(input_data: SimpleInput) -> SimpleOutput:
        return SimpleOutput(result=f"async_{input_data.value}")

    step_obj = STEP_REGISTRY["async_string"]
    result = await step_obj.on_invoke_step('{"input_data": {"value": "test"}}', "{}")
    assert result.result == "async_test"


@pytest.mark.asyncio
async def test_async_step_complex_input():
    """Test async step with complex nested input."""

    @step(name="async_complex")
    async def async_complex(input_data: ComplexInput) -> SimpleOutput:
        return SimpleOutput(result=f"async_{input_data.name}_{input_data.age}")

    step_obj = STEP_REGISTRY["async_complex"]
    result = await step_obj.on_invoke_step(
        '{"input_data": {"name": "Jane", "age": 25, "active": true, '
        '"tags": ["tag1"], "metadata": {}, "nested": {"outer": "out", "inner": {"value": "in"}}}}',
        "{}",
    )
    assert result.result == "async_Jane_25"


@pytest.mark.asyncio
async def test_async_step_with_await_operations():
    """Test async step that performs async operations."""
    import asyncio

    @step(name="async_operations")
    async def async_operations(input_data: SimpleInput) -> SimpleOutput:
        await asyncio.sleep(0.01)  # Simulate async work
        return SimpleOutput(result=f"delayed_{input_data.value}")

    step_obj = STEP_REGISTRY["async_operations"]
    result = await step_obj.on_invoke_step('{"input_data": {"value": "test"}}', "{}")
    assert result.result == "delayed_test"


@pytest.mark.asyncio
async def test_async_step_with_step_results():
    """Test async step that uses results from previous steps."""

    @step(name="async_step_a")
    async def async_step_a() -> SimpleOutput:
        return SimpleOutput(result="async_from_a")

    @step(name="async_step_b", depends_on=["async_step_a"])
    async def async_step_b(
        input_data: SimpleInput,
        async_step_a_result: Annotated[SimpleOutput, step_result("async_step_a")],
    ) -> SimpleOutput:
        return SimpleOutput(
            result=f"async_{input_data.value}_{async_step_a_result.result}"
        )

    step_obj = STEP_REGISTRY["async_step_b"]
    result = await step_obj.on_invoke_step(
        '{"input_data": {"value": "test"}}',
        '{"async_step_a": {"result": "async_from_a"}}',
    )
    assert result.result == "async_test_async_from_a"


# ========== Error Cases ==========


def test_invalid_json_input():
    """Test that invalid JSON input raises an error."""

    @step(name="error_invalid_json")
    def error_invalid_json(input_data: SimpleInput) -> SimpleOutput:
        return SimpleOutput(result="ok")

    step_obj = STEP_REGISTRY["error_invalid_json"]
    with pytest.raises(StepError, match="Invalid JSON input"):
        asyncio.run(step_obj.on_invoke_step("not json", "{}"))


def test_missing_required_field():
    """Test that missing required fields raise validation errors."""

    @step(name="error_missing_field")
    def error_missing_field(input_data: SimpleInput) -> SimpleOutput:
        return SimpleOutput(result="ok")

    step_obj = STEP_REGISTRY["error_missing_field"]
    with pytest.raises(StepError, match="Invalid JSON input"):
        asyncio.run(step_obj.on_invoke_step('{"input_data": {}}', "{}"))


def test_invalid_field_type():
    """Test that invalid field types raise validation errors."""

    @step(name="error_invalid_type")
    def error_invalid_type(input_data: SimpleInput) -> SimpleOutput:
        return SimpleOutput(result="ok")

    step_obj = STEP_REGISTRY["error_invalid_type"]
    with pytest.raises(StepError, match="Invalid JSON input"):
        asyncio.run(step_obj.on_invoke_step('{"input_data": {"value": 123}}', "{}"))


def test_missing_step_result():
    """Test that missing step results raise an error when required."""

    @step(name="error_missing_result", depends_on=["missing_step"])
    def error_missing_result(
        input_data: SimpleInput,
        missing: Annotated[SimpleOutput, step_result("missing_step")],
    ) -> SimpleOutput:
        return SimpleOutput(result="ok")

    step_obj = STEP_REGISTRY["error_missing_result"]
    # This should work if the step result is provided
    result = asyncio.run(
        step_obj.on_invoke_step(
            '{"input_data": {"value": "test"}}',
            '{"missing_step": {"result": "found"}}',
        )
    )
    assert result.result == "ok"


def test_empty_input():
    """Test step with empty input (both empty dict and empty string)."""

    @step(name="empty_input")
    def empty_input() -> str:
        return "empty_ok"

    step_obj = STEP_REGISTRY["empty_input"]
    result = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    assert result == "empty_ok"

    result = asyncio.run(step_obj.on_invoke_step("", ""))
    assert result == "empty_ok"


def test_none_values_in_optional_fields():
    """Test that None values work in optional fields."""

    @step(name="none_optional")
    def none_optional(input_data: OptionalInput) -> SimpleOutput:
        return SimpleOutput(
            result=f"{input_data.required}_{input_data.optional is None}"
        )

    step_obj = STEP_REGISTRY["none_optional"]
    result = asyncio.run(
        step_obj.on_invoke_step(
            '{"input_data": {"required": "req", "optional": null}}', "{}"
        )
    )
    assert result.result == "req_True"


# ========== Edge Cases ==========


def test_edge_cases():
    """Test step with various edge cases (large input, special chars, unicode, edge numbers)."""
    import json

    @step(name="edge_cases")
    def edge_cases(input_data: SimpleInput) -> SimpleOutput:
        return SimpleOutput(result=f"processed_{len(input_data.value)}")

    step_obj = STEP_REGISTRY["edge_cases"]

    # Test large input
    large_value = "x" * 10000
    result = asyncio.run(
        step_obj.on_invoke_step(f'{{"input_data": {{"value": "{large_value}"}}}}', "{}")
    )
    assert result.result == "processed_10000"

    # Test special characters
    special_value = 'test with "quotes" and \n newlines and \t tabs'
    input_json = json.dumps({"input_data": {"value": special_value}})
    result = asyncio.run(step_obj.on_invoke_step(input_json, "{}"))
    assert result.result == f"processed_{len(special_value)}"

    # Test unicode
    unicode_value = "测试 🎉 émoji"
    input_json = json.dumps(
        {"input_data": {"value": unicode_value}}, ensure_ascii=False
    )
    result = asyncio.run(step_obj.on_invoke_step(input_json, "{}"))
    assert result.result == f"processed_{len(unicode_value)}"


# ========== Direct Function Invocation Tests ==========


def test_direct_invocation():
    """Test that decorated step functions can be called directly (sync and async)."""

    # Sync step with parameters
    @step(name="direct_sync")
    def direct_sync(input_data: SimpleInput) -> SimpleOutput:
        return SimpleOutput(result=f"direct_{input_data.value}")

    assert "direct_sync" in STEP_REGISTRY
    result = direct_sync(SimpleInput(value="test"))
    assert result.result == "direct_test"

    # Sync step without parameters
    @step(name="direct_sync_no_params")
    def direct_sync_no_params() -> str:
        return "direct_result"

    result = direct_sync_no_params()
    assert result == "direct_result"

    # Sync step with multiple parameters and defaults
    @step(name="direct_multi")
    def direct_multi(first: str, second: int, third: bool = True) -> SimpleOutput:
        return SimpleOutput(result=f"{first}_{second}_{third}")

    result = direct_multi("hello", 42, False)
    assert result.result == "hello_42_False"
    result = direct_multi(first="world", second=100)
    assert result.result == "world_100_True"


@pytest.mark.asyncio
async def test_direct_async_invocation():
    """Test that decorated async step functions can be called directly."""

    @step(name="direct_async")
    async def direct_async(input_data: SimpleInput) -> SimpleOutput:
        return SimpleOutput(result=f"direct_async_{input_data.value}")

    assert "direct_async" in STEP_REGISTRY
    result = await direct_async(SimpleInput(value="test"))
    assert result.result == "direct_async_test"

    @step(name="direct_async_no_params")
    async def direct_async_no_params() -> str:
        return "direct_async_result"

    result = await direct_async_no_params()
    assert result == "direct_async_result"

    # Test with step results
    @step(name="direct_async_dep_a")
    async def direct_async_dep_a() -> SimpleOutput:
        return SimpleOutput(result="from_a")

    @step(name="direct_async_dep_b", depends_on=["direct_async_dep_a"])
    async def direct_async_dep_b(
        input_data: SimpleInput,
        direct_async_dep_a_result: Annotated[
            SimpleOutput, step_result("direct_async_dep_a")
        ],
    ) -> SimpleOutput:
        return SimpleOutput(
            result=f"{input_data.value}_{direct_async_dep_a_result.result}"
        )

    result_a = await direct_async_dep_a()
    result_b = await direct_async_dep_b(
        SimpleInput(value="test"), direct_async_dep_a_result=result_a
    )
    assert result_b.result == "test_from_a"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
