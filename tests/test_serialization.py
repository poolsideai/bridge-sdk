"""Tests for return value serialization with various return types."""

import asyncio
import json
import pytest
from typing import Optional, Union, List, Dict, Any
from pydantic import BaseModel
from dataclasses import dataclass
from enum import Enum

from lib import step, STEP_REGISTRY


# Test Pydantic models
class SimpleModel(BaseModel):
    value: str


class NestedModel(BaseModel):
    outer: str
    inner: SimpleModel


class ComplexModel(BaseModel):
    name: str
    age: int
    active: bool
    tags: List[str]
    metadata: Dict[str, Any]
    nested: NestedModel


class OptionalModel(BaseModel):
    required: str
    optional: Optional[str] = None
    optional_with_default: int = 42


class UnionModel(BaseModel):
    value: Union[str, int]


class EnumModel(BaseModel):
    class Status(str, Enum):
        PENDING = "pending"
        ACTIVE = "active"
        INACTIVE = "inactive"

    status: Status


# Dataclass for testing
@dataclass
class SimpleDataclass:
    value: str
    number: int


@pytest.fixture(autouse=True)
def clear_registry():
    """Clear the step registry before each test."""
    STEP_REGISTRY.clear()
    yield
    STEP_REGISTRY.clear()


# ========== Primitive Types ==========


def test_return_string():
    """Test serialization of string return type."""

    @step(name="return_string")
    def return_string() -> str:
        return "hello world"

    step_obj = STEP_REGISTRY["return_string"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result == "hello world"


def test_return_int():
    """Test serialization of int return type."""

    @step(name="return_int")
    def return_int() -> int:
        return 42

    step_obj = STEP_REGISTRY["return_int"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result == 42


def test_return_float():
    """Test serialization of float return type."""

    @step(name="return_float")
    def return_float() -> float:
        return 3.14159

    step_obj = STEP_REGISTRY["return_float"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result == 3.14159


def test_return_bool():
    """Test serialization of bool return type."""

    @step(name="return_bool")
    def return_bool() -> bool:
        return True

    step_obj = STEP_REGISTRY["return_bool"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result is True


def test_return_none():
    """Test serialization of None return type."""

    @step(name="return_none")
    def return_none() -> None:
        return None

    step_obj = STEP_REGISTRY["return_none"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result is None


# ========== Collections ==========


def test_return_list():
    """Test serialization of list return type."""

    @step(name="return_list")
    def return_list() -> List[str]:
        return ["a", "b", "c"]

    step_obj = STEP_REGISTRY["return_list"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result == ["a", "b", "c"]


def test_return_dict():
    """Test serialization of dict return type."""

    @step(name="return_dict")
    def return_dict() -> Dict[str, Any]:
        return {"key1": "value1", "key2": 42, "key3": True}

    step_obj = STEP_REGISTRY["return_dict"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result == {"key1": "value1", "key2": 42, "key3": True}


def test_return_nested_list():
    """Test serialization of nested list return type."""

    @step(name="return_nested_list")
    def return_nested_list() -> List[List[int]]:
        return [[1, 2], [3, 4], [5, 6]]

    step_obj = STEP_REGISTRY["return_nested_list"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result == [[1, 2], [3, 4], [5, 6]]


def test_return_nested_dict():
    """Test serialization of nested dict return type."""

    @step(name="return_nested_dict")
    def return_nested_dict() -> Dict[str, Dict[str, int]]:
        return {"outer": {"inner": 42}}

    step_obj = STEP_REGISTRY["return_nested_dict"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result == {"outer": {"inner": 42}}


# ========== Pydantic Models ==========


def test_return_pydantic_model():
    """Test serialization of Pydantic model return type."""

    @step(name="return_pydantic")
    def return_pydantic() -> SimpleModel:
        return SimpleModel(value="test")

    step_obj = STEP_REGISTRY["return_pydantic"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = SimpleModel.model_validate_json(result_json)
    assert result.value == "test"


def test_return_nested_pydantic_model():
    """Test serialization of nested Pydantic model return type."""

    @step(name="return_nested_pydantic")
    def return_nested_pydantic() -> NestedModel:
        return NestedModel(outer="outer", inner=SimpleModel(value="inner"))

    step_obj = STEP_REGISTRY["return_nested_pydantic"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = NestedModel.model_validate_json(result_json)
    assert result.outer == "outer"
    assert result.inner.value == "inner"


def test_return_complex_pydantic_model():
    """Test serialization of complex Pydantic model return type."""

    @step(name="return_complex_pydantic")
    def return_complex_pydantic() -> ComplexModel:
        return ComplexModel(
            name="John",
            age=30,
            active=True,
            tags=["tag1", "tag2"],
            metadata={"key": "value"},
            nested=NestedModel(outer="out", inner=SimpleModel(value="in")),
        )

    step_obj = STEP_REGISTRY["return_complex_pydantic"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = ComplexModel.model_validate_json(result_json)
    assert result.name == "John"
    assert result.age == 30
    assert result.active is True
    assert result.tags == ["tag1", "tag2"]
    assert result.metadata == {"key": "value"}
    assert result.nested.outer == "out"
    assert result.nested.inner.value == "in"


def test_return_optional_pydantic_model():
    """Test serialization of Pydantic model with optional fields."""

    @step(name="return_optional_pydantic")
    def return_optional_pydantic() -> OptionalModel:
        return OptionalModel(required="req", optional=None)

    step_obj = STEP_REGISTRY["return_optional_pydantic"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = OptionalModel.model_validate_json(result_json)
    assert result.required == "req"
    assert result.optional is None
    assert result.optional_with_default == 42


def test_return_union_pydantic_model():
    """Test serialization of Pydantic model with union field."""

    @step(name="return_union_pydantic")
    def return_union_pydantic() -> UnionModel:
        return UnionModel(value="string")

    step_obj = STEP_REGISTRY["return_union_pydantic"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = UnionModel.model_validate_json(result_json)
    assert result.value == "string"

    @step(name="return_union_pydantic_int")
    def return_union_pydantic_int() -> UnionModel:
        return UnionModel(value=42)

    step_obj = STEP_REGISTRY["return_union_pydantic_int"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = UnionModel.model_validate_json(result_json)
    assert result.value == 42


def test_return_enum_pydantic_model():
    """Test serialization of Pydantic model with enum field."""

    @step(name="return_enum_pydantic")
    def return_enum_pydantic() -> EnumModel:
        return EnumModel(status=EnumModel.Status.ACTIVE)

    step_obj = STEP_REGISTRY["return_enum_pydantic"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = EnumModel.model_validate_json(result_json)
    assert result.status == EnumModel.Status.ACTIVE


# ========== Type Annotations ==========


def test_return_with_union_type():
    """Test serialization with Union return type annotation."""

    @step(name="return_union")
    def return_union() -> Union[str, int]:
        return "string"

    step_obj = STEP_REGISTRY["return_union"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result == "string"

    @step(name="return_union_int")
    def return_union_int() -> Union[str, int]:
        return 42

    step_obj = STEP_REGISTRY["return_union_int"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result == 42


def test_return_with_optional_type():
    """Test serialization with Optional return type annotation."""

    @step(name="return_optional")
    def return_optional() -> Optional[str]:
        return "value"

    step_obj = STEP_REGISTRY["return_optional"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result == "value"

    @step(name="return_optional_none")
    def return_optional_none() -> Optional[str]:
        return None

    step_obj = STEP_REGISTRY["return_optional_none"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result is None


def test_return_with_list_type():
    """Test serialization with List return type annotation."""

    @step(name="return_list_type")
    def return_list_type() -> List[int]:
        return [1, 2, 3, 4, 5]

    step_obj = STEP_REGISTRY["return_list_type"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result == [1, 2, 3, 4, 5]


def test_return_with_dict_type():
    """Test serialization with Dict return type annotation."""

    @step(name="return_dict_type")
    def return_dict_type() -> Dict[str, int]:
        return {"a": 1, "b": 2, "c": 3}

    step_obj = STEP_REGISTRY["return_dict_type"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result == {"a": 1, "b": 2, "c": 3}


# ========== No Type Annotation (Any) ==========


def test_return_no_annotation_string():
    """Test serialization with no return type annotation (returns string)."""

    @step(name="return_no_annotation_string")
    def return_no_annotation_string():
        return "no annotation"

    step_obj = STEP_REGISTRY["return_no_annotation_string"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result == "no annotation"


def test_return_no_annotation_dict():
    """Test serialization with no return type annotation (returns dict)."""

    @step(name="return_no_annotation_dict")
    def return_no_annotation_dict():
        return {"key": "value"}

    step_obj = STEP_REGISTRY["return_no_annotation_dict"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result == {"key": "value"}


def test_return_no_annotation_pydantic():
    """Test serialization with no return type annotation (returns Pydantic model)."""

    @step(name="return_no_annotation_pydantic")
    def return_no_annotation_pydantic():
        return SimpleModel(value="no annotation")

    step_obj = STEP_REGISTRY["return_no_annotation_pydantic"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = SimpleModel.model_validate_json(result_json)
    assert result.value == "no annotation"


# ========== Dataclasses ==========


def test_return_dataclass():
    """Test serialization of dataclass return type."""

    @step(name="return_dataclass")
    def return_dataclass() -> SimpleDataclass:
        return SimpleDataclass(value="test", number=42)

    step_obj = STEP_REGISTRY["return_dataclass"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    # Dataclass should be serialized as dict via __dict__
    assert result == {"value": "test", "number": 42}


# ========== Edge Cases ==========


def test_return_empty_list():
    """Test serialization of empty list."""

    @step(name="return_empty_list")
    def return_empty_list() -> List[str]:
        return []

    step_obj = STEP_REGISTRY["return_empty_list"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result == []


def test_return_empty_dict():
    """Test serialization of empty dict."""

    @step(name="return_empty_dict")
    def return_empty_dict() -> Dict[str, Any]:
        return {}

    step_obj = STEP_REGISTRY["return_empty_dict"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result == {}


def test_return_list_with_none():
    """Test serialization of list containing None values."""

    @step(name="return_list_with_none")
    def return_list_with_none() -> List[Optional[str]]:
        return ["value", None, "another"]

    step_obj = STEP_REGISTRY["return_list_with_none"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result == ["value", None, "another"]


def test_return_dict_with_none():
    """Test serialization of dict containing None values."""

    @step(name="return_dict_with_none")
    def return_dict_with_none() -> Dict[str, Optional[str]]:
        return {"key1": "value", "key2": None, "key3": "another"}

    step_obj = STEP_REGISTRY["return_dict_with_none"]
    result_json = asyncio.run(step_obj.on_invoke_step("{}", "{}"))
    result = json.loads(result_json)
    assert result == {"key1": "value", "key2": None, "key3": "another"}


# ========== Async Functions ==========


@pytest.mark.asyncio
async def test_async_return_string():
    """Test serialization of string return from async function."""

    @step(name="async_return_string")
    async def async_return_string() -> str:
        return "async string"

    step_obj = STEP_REGISTRY["async_return_string"]
    result_json = await step_obj.on_invoke_step("{}", "{}")
    result = json.loads(result_json)
    assert result == "async string"


@pytest.mark.asyncio
async def test_async_return_pydantic():
    """Test serialization of Pydantic model return from async function."""

    @step(name="async_return_pydantic")
    async def async_return_pydantic() -> SimpleModel:
        return SimpleModel(value="async test")

    step_obj = STEP_REGISTRY["async_return_pydantic"]
    result_json = await step_obj.on_invoke_step("{}", "{}")
    result = SimpleModel.model_validate_json(result_json)
    assert result.value == "async test"


@pytest.mark.asyncio
async def test_async_return_list():
    """Test serialization of list return from async function."""

    @step(name="async_return_list")
    async def async_return_list() -> List[int]:
        return [1, 2, 3]

    step_obj = STEP_REGISTRY["async_return_list"]
    result_json = await step_obj.on_invoke_step("{}", "{}")
    result = json.loads(result_json)
    assert result == [1, 2, 3]
