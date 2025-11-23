from dataclasses import dataclass
import inspect
from typing import Annotated, Any, Callable, get_args, get_origin, get_type_hints

from pydantic import BaseModel, Field, create_model
from pydantic.fields import FieldInfo


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
    signature: inspect.Signature
    """The signature of the function."""

    def to_call_args(self, data: BaseModel) -> tuple[list[Any], dict[str, Any]]:
        """
        Converts validated data from the Pydantic model into (args, kwargs), suitable for calling
        the original function.
        """
        positional_args: list[Any] = []
        keyword_args: dict[str, Any] = {}
        seen_var_positional = False

        for idx, (name, param) in enumerate(self.signature.parameters.items()):
            value = getattr(data, name, None)
            if param.kind == param.VAR_POSITIONAL:
                # e.g. *args: extend positional args and mark that *args is now seen
                positional_args.extend(value or [])
                seen_var_positional = True
            elif param.kind == param.VAR_KEYWORD:
                # e.g. **kwargs handling
                keyword_args.update(value or {})
            elif param.kind in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD):
                # Before *args, add to positional args. After *args, add to keyword args.
                if not seen_var_positional:
                    positional_args.append(value)
                else:
                    keyword_args[name] = value
            else:
                # For KEYWORD_ONLY parameters, always use keyword args.
                keyword_args[name] = value
        return positional_args, keyword_args


def _strip_annotated(annotation: Any) -> tuple[Any, tuple[Any, ...]]:
    """Returns the underlying annotation and any metadata from typing.Annotated."""

    metadata: tuple[Any, ...] = ()
    ann = annotation

    while get_origin(ann) is Annotated:
        args = get_args(ann)
        if not args:
            break
        ann = args[0]
        metadata = (*metadata, *args[1:])

    return ann, metadata


def function_schema(func: Callable[..., Any]) -> FunctionSchema:
    """Create a StepData object from a step function."""
    # Get the line number where the function is defined

    type_hints_with_extras = get_type_hints(func, include_extras=True)
    type_hints: dict[str, Any] = {}
    param_annotations: dict[str, tuple[str, ...]] = {}

    for param_name, annotation in type_hints_with_extras.items():
        stripped_ann, annotation_metadata = _strip_annotated(annotation)
        type_hints[param_name] = stripped_ann
        param_annotations[param_name] = annotation_metadata

    # Name override takes precedence over function name
    func_name = func.__name__

    sig = inspect.signature(func)
    params = list(sig.parameters.items())

    fields: dict[str, Any] = {}

    for name, param in params:
        ann = type_hints.get(name, param.annotation)
        default = param.default

        # If there's no type hint, assume `Any`
        if ann == inspect._empty:
            ann = Any

        # Handle different parameter kinds
        if param.kind == param.VAR_POSITIONAL:
            # e.g. *args: extend positional args
            if get_origin(ann) is tuple:
                # e.g. def foo(*args: tuple[int, ...]) -> treat as List[int]
                args_of_tuple = get_args(ann)
                if len(args_of_tuple) == 2 and args_of_tuple[1] is Ellipsis:
                    ann = list[args_of_tuple[0]]  # type: ignore
                else:
                    ann = list[Any]
            else:
                # If user wrote *args: int, treat as List[int]
                ann = list[ann]  # type: ignore

            # Default factory to empty list
            fields[name] = (
                ann,
                Field(default_factory=list),
            )

        elif param.kind == param.VAR_KEYWORD:
            # **kwargs handling
            if get_origin(ann) is dict:
                # e.g. def foo(**kwargs: dict[str, int])
                dict_args = get_args(ann)
                if len(dict_args) == 2:
                    ann = dict[dict_args[0], dict_args[1]]  # type: ignore
                else:
                    ann = dict[str, Any]
            else:
                # e.g. def foo(**kwargs: int) -> Dict[str, int]
                ann = dict[str, ann]  # type: ignore

            fields[name] = (
                ann,
                Field(default_factory=dict),
            )

        else:
            # Normal parameter
            if default == inspect._empty:
                # Required field
                fields[name] = (
                    ann,
                    Field(...),
                )
            elif isinstance(default, FieldInfo):
                # Parameter with a default value that is a Field(...)
                fields[name] = (
                    ann,
                    FieldInfo.merge_field_infos(default, default.description),
                )
            else:
                # Parameter with a default value
                fields[name] = (
                    ann,
                    Field(default=default),
                )

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
        signature=sig,
    )
