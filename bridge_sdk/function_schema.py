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

from dataclasses import dataclass
import inspect
from typing import Annotated, Any, Callable, get_args, get_origin, get_type_hints

from pydantic import BaseModel, Field, create_model


@dataclass
class FunctionSchema:
    """
    Captures the schema for a python function.
    """

    name: str
    """The name of the function."""
    params_pydantic_model: type[BaseModel]
    """A Pydantic model that represents the function's parameters."""
    params_json_schema: dict[str, Any]
    """The JSON schema for the function's parameters, derived from the Pydantic model."""
    param_annotations: dict[str, tuple[str, ...]]
    """A map of the param name to any annotations."""
    return_json_schema: dict[str, Any]
    """The JSON schema for the function's return."""
    return_type: Any
    """The return type annotation of the function."""
    signature: inspect.Signature
    """The signature of the function."""


def create_function_schema(func: Callable[..., Any]) -> FunctionSchema:
    """Create a FunctionSchema from a function."""
    func_name = func.__name__
    type_hints = get_type_hints(func, include_extras=True)
    sig = inspect.signature(func)

    # Extract Annotated metadata for step_result detection
    param_annotations: dict[str, tuple[str, ...]] = {}
    for name, hint in type_hints.items():
        if get_origin(hint) is Annotated:
            param_annotations[name] = get_args(hint)[1:]

    fields: dict[str, Any] = {}
    for name, param in sig.parameters.items():
        ann = type_hints.get(name, param.annotation)
        if ann == inspect._empty:
            ann = str
        default = param.default
        fields[name] = (ann, Field(...) if default == inspect._empty else Field(default=default))

    # 3. Dynamically build a Pydantic model
    dynamic_model = create_model(f"{func_name}_args", __base__=BaseModel, **fields)

    # 4. Build JSON schema from that model
    json_schema = dynamic_model.model_json_schema()

    # 5. Build return type JSON schema
    return_type = type_hints.get("return", Any)
    if return_type == inspect.Signature.empty:
        return_type = Any

    try:
        dynamic_return_model = create_model(
            f"{func_name}_return",
            __base__=BaseModel,
            return_type=(return_type, Field(...)),
        )
        full_return_schema = dynamic_return_model.model_json_schema()
        # Extract just the "return_type" field schema from the properties
        if (
            "properties" in full_return_schema
            and "return_type" in full_return_schema["properties"]
        ):
            return_json_schema = full_return_schema["properties"]["return_type"]
            # Preserve $defs if they exist, as they may be needed for $ref references
            if "$defs" in full_return_schema:
                return_json_schema = {
                    **return_json_schema,
                    "$defs": full_return_schema["$defs"],
                }
        else:
            return_json_schema = full_return_schema
    except Exception:
        return_json_schema = {}

    return FunctionSchema(
        name=func_name,
        params_pydantic_model=dynamic_model,
        params_json_schema=json_schema,
        param_annotations=param_annotations,
        return_json_schema=return_json_schema,
        return_type=return_type,
        signature=sig,
    )
