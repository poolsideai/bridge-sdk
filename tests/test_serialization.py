"""Tests for return value serialization with various return types."""

import asyncio
import json
import pytest
from typing import Optional, Union, List, Dict, Any
from pydantic import BaseModel
from dataclasses import dataclass
from enum import Enum

from lib import step, STEP_REGISTRY


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


class Status(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"


class EnumModel(BaseModel):
    status: Status


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


def test_return_primitives():
    """Test serialization of primitive return types."""

    @step(name="return_string")
    def return_string() -> str:
        return "hello"

    @step(name="return_int")
    def return_int() -> int:
        return 42

    @step(name="return_float")
    def return_float() -> float:
        return 3.14

    @step(name="return_bool")
    def return_bool() -> bool:
        return True

    @step(name="return_none")
    def return_none() -> None:
        return None

    assert (
        json.loads(
            asyncio.run(STEP_REGISTRY["return_string"].on_invoke_step("{}", "{}"))
        )
        == "hello"
    )
    assert (
        json.loads(asyncio.run(STEP_REGISTRY["return_int"].on_invoke_step("{}", "{}")))
        == 42
    )
    assert (
        json.loads(
            asyncio.run(STEP_REGISTRY["return_float"].on_invoke_step("{}", "{}"))
        )
        == 3.14
    )
    assert (
        json.loads(asyncio.run(STEP_REGISTRY["return_bool"].on_invoke_step("{}", "{}")))
        is True
    )
    assert (
        json.loads(asyncio.run(STEP_REGISTRY["return_none"].on_invoke_step("{}", "{}")))
        is None
    )


# ========== Collections ==========


def test_return_collections():
    """Test serialization of collection return types."""

    @step(name="return_list")
    def return_list() -> List[str]:
        return ["a", "b", "c"]

    @step(name="return_dict")
    def return_dict() -> Dict[str, Any]:
        return {"key1": "value1", "key2": 42}

    @step(name="return_nested")
    def return_nested() -> Dict[str, List[int]]:
        return {"nums": [1, 2, 3]}

    @step(name="return_empty_list")
    def return_empty_list() -> List[str]:
        return []

    @step(name="return_empty_dict")
    def return_empty_dict() -> Dict[str, Any]:
        return {}

    assert json.loads(
        asyncio.run(STEP_REGISTRY["return_list"].on_invoke_step("{}", "{}"))
    ) == ["a", "b", "c"]
    assert json.loads(
        asyncio.run(STEP_REGISTRY["return_dict"].on_invoke_step("{}", "{}"))
    ) == {"key1": "value1", "key2": 42}
    assert json.loads(
        asyncio.run(STEP_REGISTRY["return_nested"].on_invoke_step("{}", "{}"))
    ) == {"nums": [1, 2, 3]}
    assert (
        json.loads(
            asyncio.run(STEP_REGISTRY["return_empty_list"].on_invoke_step("{}", "{}"))
        )
        == []
    )
    assert (
        json.loads(
            asyncio.run(STEP_REGISTRY["return_empty_dict"].on_invoke_step("{}", "{}"))
        )
        == {}
    )


# ========== Pydantic Models ==========


def test_return_pydantic_models():
    """Test serialization of Pydantic model return types."""

    @step(name="return_simple")
    def return_simple() -> SimpleModel:
        return SimpleModel(value="test")

    @step(name="return_nested")
    def return_nested() -> NestedModel:
        return NestedModel(outer="out", inner=SimpleModel(value="in"))

    @step(name="return_complex")
    def return_complex() -> ComplexModel:
        return ComplexModel(
            name="John",
            age=30,
            active=True,
            tags=["a", "b"],
            metadata={"key": "val"},
            nested=NestedModel(outer="out", inner=SimpleModel(value="in")),
        )

    @step(name="return_optional")
    def return_optional() -> OptionalModel:
        return OptionalModel(required="req", optional=None)

    @step(name="return_enum")
    def return_enum() -> EnumModel:
        return EnumModel(status=Status.ACTIVE)

    result = SimpleModel.model_validate_json(
        asyncio.run(STEP_REGISTRY["return_simple"].on_invoke_step("{}", "{}"))
    )
    assert result.value == "test"

    result = NestedModel.model_validate_json(
        asyncio.run(STEP_REGISTRY["return_nested"].on_invoke_step("{}", "{}"))
    )
    assert result.outer == "out"
    assert result.inner.value == "in"

    result = ComplexModel.model_validate_json(
        asyncio.run(STEP_REGISTRY["return_complex"].on_invoke_step("{}", "{}"))
    )
    assert result.name == "John"
    assert result.age == 30
    assert result.tags == ["a", "b"]
    assert result.nested.inner.value == "in"

    result = OptionalModel.model_validate_json(
        asyncio.run(STEP_REGISTRY["return_optional"].on_invoke_step("{}", "{}"))
    )
    assert result.required == "req"
    assert result.optional is None

    result = EnumModel.model_validate_json(
        asyncio.run(STEP_REGISTRY["return_enum"].on_invoke_step("{}", "{}"))
    )
    assert result.status == Status.ACTIVE


# ========== Union and Optional Types ==========


def test_return_union_and_optional():
    """Test serialization with Union and Optional return types."""

    @step(name="return_union_str")
    def return_union_str() -> Union[str, int]:
        return "string"

    @step(name="return_union_int")
    def return_union_int() -> Union[str, int]:
        return 42

    @step(name="return_optional_value")
    def return_optional_value() -> Optional[str]:
        return "value"

    @step(name="return_optional_none")
    def return_optional_none() -> Optional[str]:
        return None

    assert (
        json.loads(
            asyncio.run(STEP_REGISTRY["return_union_str"].on_invoke_step("{}", "{}"))
        )
        == "string"
    )
    assert (
        json.loads(
            asyncio.run(STEP_REGISTRY["return_union_int"].on_invoke_step("{}", "{}"))
        )
        == 42
    )
    assert (
        json.loads(
            asyncio.run(
                STEP_REGISTRY["return_optional_value"].on_invoke_step("{}", "{}")
            )
        )
        == "value"
    )
    assert (
        json.loads(
            asyncio.run(
                STEP_REGISTRY["return_optional_none"].on_invoke_step("{}", "{}")
            )
        )
        is None
    )


# ========== No Type Annotation ==========


def test_return_no_annotation():
    """Test serialization with no return type annotation."""

    @step(name="return_no_annotation_str")
    def return_no_annotation_str():
        return "no annotation"

    @step(name="return_no_annotation_dict")
    def return_no_annotation_dict():
        return {"key": "value"}

    @step(name="return_no_annotation_pydantic")
    def return_no_annotation_pydantic():
        return SimpleModel(value="no annotation")

    assert (
        json.loads(
            asyncio.run(
                STEP_REGISTRY["return_no_annotation_str"].on_invoke_step("{}", "{}")
            )
        )
        == "no annotation"
    )
    assert json.loads(
        asyncio.run(
            STEP_REGISTRY["return_no_annotation_dict"].on_invoke_step("{}", "{}")
        )
    ) == {"key": "value"}
    result = SimpleModel.model_validate_json(
        asyncio.run(
            STEP_REGISTRY["return_no_annotation_pydantic"].on_invoke_step("{}", "{}")
        )
    )
    assert result.value == "no annotation"


# ========== Dataclasses ==========


def test_return_dataclass():
    """Test serialization of dataclass return type."""

    @step(name="return_dataclass")
    def return_dataclass() -> SimpleDataclass:
        return SimpleDataclass(value="test", number=42)

    result = json.loads(
        asyncio.run(STEP_REGISTRY["return_dataclass"].on_invoke_step("{}", "{}"))
    )
    assert result == {"value": "test", "number": 42}


# ========== Async Functions ==========


@pytest.mark.asyncio
async def test_async_return_serialization():
    """Test serialization works correctly for async functions."""

    @step(name="async_return_str")
    async def async_return_str() -> str:
        return "async string"

    @step(name="async_return_pydantic")
    async def async_return_pydantic() -> SimpleModel:
        return SimpleModel(value="async test")

    @step(name="async_return_list")
    async def async_return_list() -> List[int]:
        return [1, 2, 3]

    assert (
        json.loads(await STEP_REGISTRY["async_return_str"].on_invoke_step("{}", "{}"))
        == "async string"
    )
    result = SimpleModel.model_validate_json(
        await STEP_REGISTRY["async_return_pydantic"].on_invoke_step("{}", "{}")
    )
    assert result.value == "async test"
    assert json.loads(
        await STEP_REGISTRY["async_return_list"].on_invoke_step("{}", "{}")
    ) == [1, 2, 3]


# ========== Edge Cases ==========


def test_return_collections_with_none():
    """Test serialization of collections containing None values."""

    @step(name="list_with_none")
    def list_with_none() -> List[Optional[str]]:
        return ["value", None, "another"]

    @step(name="dict_with_none")
    def dict_with_none() -> Dict[str, Optional[str]]:
        return {"key1": "value", "key2": None}

    assert json.loads(
        asyncio.run(STEP_REGISTRY["list_with_none"].on_invoke_step("{}", "{}"))
    ) == ["value", None, "another"]
    assert json.loads(
        asyncio.run(STEP_REGISTRY["dict_with_none"].on_invoke_step("{}", "{}"))
    ) == {"key1": "value", "key2": None}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
