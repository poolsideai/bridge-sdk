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

"""Tests for the eval functionality."""

import json
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError
from typing import Any
from typing_extensions import TypedDict

from bridge_sdk import (
    EVAL_REGISTRY,
    STEP_REGISTRY,
    PIPELINE_REGISTRY,
    EvalData,
    EvalFunction,
    EvalResult,
    StepEvalContext,
    PipelineEvalContext,
    bridge_eval,
    EvalBindingData,
    Condition,
    always,
    never,
    on_branch,
    sample,
    step,
    Pipeline,
)
from bridge_sdk.eval_function import (
    _build_step_eval_context,
    _build_pipeline_eval_context,
    _serialize_eval_result,
)


@pytest.fixture(autouse=True)
def clear_registries():
    """Clear all registries before each test."""
    EVAL_REGISTRY.clear()
    STEP_REGISTRY.clear()
    PIPELINE_REGISTRY.clear()
    yield
    EVAL_REGISTRY.clear()
    STEP_REGISTRY.clear()
    PIPELINE_REGISTRY.clear()


# --- Condition tests ---


class TestConditions:
    def test_always(self):
        assert always().to_cel() == "true"

    def test_never(self):
        assert never().to_cel() == "false"

    def test_on_branch(self):
        assert on_branch("main").to_cel() == 'metadata.branch == "main"'

    def test_sample(self):
        assert sample(0.1).to_cel() == "sample_value < 0.1"

    def test_sample_validation(self):
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            sample(1.5)
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            sample(-0.1)

    def test_sample_boundary_values(self):
        assert sample(0.0).to_cel() == "sample_value < 0.0"
        assert sample(1.0).to_cel() == "sample_value < 1.0"

    def test_and_combinator(self):
        result = (on_branch("main") & sample(0.1)).to_cel()
        assert result == '(metadata.branch == "main") && (sample_value < 0.1)'

    def test_or_combinator(self):
        result = (on_branch("main") | on_branch("staging")).to_cel()
        assert result == '(metadata.branch == "main") || (metadata.branch == "staging")'

    def test_nested_and_composes(self):
        result = (on_branch("main") & sample(0.1) & always()).to_cel()
        assert result == '((metadata.branch == "main") && (sample_value < 0.1)) && (true)'

    def test_nested_or_composes(self):
        result = (on_branch("a") | on_branch("b") | on_branch("c")).to_cel()
        assert result == '((metadata.branch == "a") || (metadata.branch == "b")) || (metadata.branch == "c")'

    def test_mixed_and_or(self):
        result = ((on_branch("main") & sample(0.1)) | always()).to_cel()
        assert result == '((metadata.branch == "main") && (sample_value < 0.1)) || (true)'


# --- @bridge_eval decorator tests ---


class QualityMetrics(TypedDict):
    accuracy: float
    followed_format: bool


class TestBridgeEvalDecorator:
    def test_register_no_parens(self):
        @bridge_eval
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        assert "my_eval" in EVAL_REGISTRY
        assert isinstance(my_eval, EvalFunction)

    def test_register_with_parens(self):
        @bridge_eval()
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        assert "my_eval" in EVAL_REGISTRY

    def test_register_with_name_override(self):
        @bridge_eval(name="custom_name")
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        assert "custom_name" in EVAL_REGISTRY
        assert "my_eval" not in EVAL_REGISTRY

    def test_register_with_rid(self):
        @bridge_eval(rid="abc-123")
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        assert EVAL_REGISTRY["my_eval"].eval_data.rid == "abc-123"

    def test_callable_passthrough(self):
        @bridge_eval
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        ctx = StepEvalContext(
            step_name="test",
            step_input=None,
            step_output=None,
            trajectory=None,
        )
        result = my_eval(ctx)
        assert isinstance(result, EvalResult)
        assert result.metrics["accuracy"] == 1.0


# --- Context type extraction tests ---


class TestContextTypeExtraction:
    def test_step_context_type(self):
        @bridge_eval
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        assert my_eval.eval_data.context_type == "step"

    def test_pipeline_context_type(self):
        @bridge_eval
        def my_eval(ctx: PipelineEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        assert my_eval.eval_data.context_type == "pipeline"

    def test_invalid_context_type(self):
        with pytest.raises(TypeError, match="first parameter must be typed"):

            @bridge_eval
            def my_eval(ctx: dict) -> EvalResult[QualityMetrics]:
                return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

    def test_missing_type_annotation(self):
        with pytest.raises(TypeError, match="must have a type annotation"):

            @bridge_eval
            def my_eval(ctx) -> EvalResult[QualityMetrics]:
                return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

    def test_no_parameters(self):
        with pytest.raises(TypeError, match="must accept at least one parameter"):

            @bridge_eval
            def my_eval() -> EvalResult[QualityMetrics]:
                return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})


# --- Schema extraction tests ---


class TestSchemaExtraction:
    def test_metrics_schema_extracted(self):
        @bridge_eval
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        schema = my_eval.eval_data.metrics_schema
        assert "properties" in schema
        assert "accuracy" in schema["properties"]
        assert "followed_format" in schema["properties"]

    def test_input_output_type_schemas_with_any(self):
        @bridge_eval
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        assert my_eval.eval_data.input_type_schema is None
        assert my_eval.eval_data.output_type_schema is None

    def test_input_output_type_schemas_with_specific_types(self):
        from pydantic import BaseModel

        class MyInput(BaseModel):
            query: str

        class MyOutput(BaseModel):
            answer: str

        @bridge_eval
        def my_eval(
            ctx: StepEvalContext[MyInput, MyOutput],
        ) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        assert my_eval.eval_data.input_type_schema is not None
        assert "properties" in my_eval.eval_data.input_type_schema
        assert "query" in my_eval.eval_data.input_type_schema["properties"]

        assert my_eval.eval_data.output_type_schema is not None
        assert "answer" in my_eval.eval_data.output_type_schema["properties"]

    def test_file_path_and_line_number(self):
        @bridge_eval
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        assert my_eval.eval_data.file_path is not None
        assert my_eval.eval_data.file_line_number is not None
        assert "test_eval.py" in my_eval.eval_data.file_path


# --- eval_bindings tests ---


class TestEvalBindings:
    def test_binding_attaches_to_step(self):
        @bridge_eval
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        @step(eval_bindings=[(my_eval, on_branch("main"))])
        def my_step(value: str) -> str:
            return value

        assert len(my_step.step_data.eval_bindings) == 1
        binding = my_step.step_data.eval_bindings[0]
        assert binding.eval_name == "my_eval"
        assert binding.condition == "metadata.branch == \"main\""

    def test_multiple_bindings(self):
        @bridge_eval
        def eval_a(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        @bridge_eval
        def eval_b(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        @step(
            eval_bindings=[
                (eval_a, on_branch("main")),
                (eval_b, sample(0.1)),
            ]
        )
        def my_step(value: str) -> str:
            return value

        assert len(my_step.step_data.eval_bindings) == 2
        names = {b.eval_name for b in my_step.step_data.eval_bindings}
        assert names == {"eval_a", "eval_b"}

    def test_default_condition_is_always(self):
        @bridge_eval
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        @step(eval_bindings=[my_eval])
        def my_step(value: str) -> str:
            return value

        assert my_step.step_data.eval_bindings[0].condition == "true"

    def test_string_eval_ref(self):
        @step(eval_bindings=["cross_repo_eval"])
        def my_step(value: str) -> str:
            return value

        assert my_step.step_data.eval_bindings[0].eval_name == "cross_repo_eval"

    def test_invalid_eval_ref_type(self):
        with pytest.raises(TypeError, match="eval_bindings entries"):

            @step(eval_bindings=[42])  # type: ignore[list-item]
            def my_step(value: str) -> str:
                return value

    def test_invalid_tuple_entry_shape(self):
        with pytest.raises(TypeError, match="tuple eval binding entries"):

            @step(eval_bindings=[("my_eval", "true", "extra")])  # type: ignore[list-item]
            def my_step(value: str) -> str:
                return value


# --- Pipeline eval_bindings tests ---


class TestPipelineEvalBindings:
    def test_pipeline_constructor_bindings(self):
        @bridge_eval
        def pipeline_eval(
            ctx: PipelineEvalContext[Any, Any],
        ) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        pipeline = Pipeline(
            name="test_pipeline",
            eval_bindings=[(pipeline_eval, always())],
        )

        assert len(pipeline._eval_bindings) == 1
        assert pipeline._eval_bindings[0].eval_name == "pipeline_eval"
        assert pipeline._eval_bindings[0].condition == "true"

    def test_pipeline_constructor_string_ref(self):
        pipeline = Pipeline(
            name="test_pipeline",
            eval_bindings=[("remote_eval", on_branch("main"))],
        )

        assert pipeline._eval_bindings[0].eval_name == "remote_eval"

    def test_pipeline_constructor_no_bindings(self):
        pipeline = Pipeline(name="test_pipeline")
        assert len(pipeline._eval_bindings) == 0


# --- DSL output tests ---


class TestDSLOutput:
    def test_eval_data_serialization(self):
        @bridge_eval
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        data = my_eval.eval_data.model_dump()
        assert data["name"] == "my_eval"
        assert data["context_type"] == "step"
        assert "metrics_schema" in data
        assert data["input_type_schema"] is None
        assert data["output_type_schema"] is None

    def test_step_data_includes_eval_bindings(self):
        @bridge_eval
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        @step(eval_bindings=[(my_eval, on_branch("main"))])
        def my_step(value: str) -> str:
            return value

        data = my_step.step_data.model_dump()
        assert "eval_bindings" in data
        assert len(data["eval_bindings"]) == 1
        assert data["eval_bindings"][0]["eval_name"] == "my_eval"

    def test_eval_binding_data_serialization(self):
        binding = EvalBindingData(
            eval_name="my_eval",
            condition="metadata.branch == \"main\"",
        )
        data = binding.model_dump()
        assert data == {
            "eval_name": "my_eval",
            "condition": "metadata.branch == \"main\"",
        }


# --- on_invoke_eval tests ---


class TestOnInvokeEval:
    @pytest.mark.asyncio
    async def test_step_eval_invocation(self):
        @bridge_eval
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(
                metrics={
                    "accuracy": 1.0 if ctx.step_output == "correct" else 0.0,
                    "followed_format": True,
                },
                result="Looks good",
            )

        context_json = json.dumps(
            {
                "step_name": "test_step",
                "step_input": "question",
                "step_output": "correct",
                "trajectory": None,
                "metadata": {
                    "step_rid": "rid-1",
                    "step_version_id": "v-1",
                    "execution_id": "exec-1",
                    "repository": "test-repo",
                    "branch": "main",
                    "commit_sha": "abc123",
                    "started_at": "2026-01-01T00:00:00",
                    "completed_at": "2026-01-01T00:01:00",
                    "duration_ms": 60000,
                },
            }
        )

        result_json = await my_eval.on_invoke_eval(context=context_json)
        result = json.loads(result_json)

        assert result["metrics"]["accuracy"] == 1.0
        assert result["metrics"]["followed_format"] is True
        assert result["result"] == {"type": "string", "string_value": "Looks good"}

    @pytest.mark.asyncio
    async def test_pipeline_eval_invocation(self):
        @bridge_eval
        def my_eval(
            ctx: PipelineEvalContext[Any, Any],
        ) -> EvalResult[QualityMetrics]:
            step_output = ctx.steps["my_step"].output
            return EvalResult(
                metrics={"accuracy": 1.0, "followed_format": step_output == "good"},
            )

        context_json = json.dumps(
            {
                "pipeline_name": "test_pipeline",
                "pipeline_input": {},
                "pipeline_output": {},
                "steps": {
                    "my_step": {
                        "step_name": "my_step",
                        "input": "in",
                        "output": "good",
                        "trajectory": None,
                        "duration_ms": 100,
                        "success": True,
                    }
                },
            }
        )

        result_json = await my_eval.on_invoke_eval(context=context_json)
        result = json.loads(result_json)

        assert result["metrics"]["accuracy"] == 1.0
        assert result["metrics"]["followed_format"] is True

    @pytest.mark.asyncio
    async def test_async_eval_function(self):
        @bridge_eval
        async def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        context_json = json.dumps(
            {
                "step_name": "test",
                "step_input": None,
                "step_output": None,
                "metadata": {},
            }
        )

        result_json = await my_eval.on_invoke_eval(context=context_json)
        result = json.loads(result_json)
        assert result["metrics"]["accuracy"] == 1.0

    @pytest.mark.asyncio
    async def test_eval_returning_non_eval_result_raises(self):
        @bridge_eval
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return {"metrics": {}}  # type: ignore[return-value]

        context_json = json.dumps(
            {"step_name": "test", "step_input": None, "step_output": None, "metadata": {}}
        )

        with pytest.raises(TypeError, match="must return an EvalResult"):
            await my_eval.on_invoke_eval(context=context_json)

    @pytest.mark.asyncio
    async def test_eval_output_omitted_when_none(self):
        @bridge_eval
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        context_json = json.dumps(
            {"step_name": "test", "step_input": None, "step_output": None, "metadata": {}}
        )

        result_json = await my_eval.on_invoke_eval(context=context_json)
        result = json.loads(result_json)
        assert "result" not in result

    @pytest.mark.asyncio
    async def test_invalid_json_context_raises(self):
        @bridge_eval
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        with pytest.raises(ValueError, match="Invalid JSON context"):
            await my_eval.on_invoke_eval(context="not valid json {{{")

    @pytest.mark.asyncio
    async def test_empty_context_string(self):
        @bridge_eval
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        result_json = await my_eval.on_invoke_eval(context="")
        result = json.loads(result_json)
        assert result["metrics"]["accuracy"] == 1.0

    @pytest.mark.asyncio
    async def test_pipeline_eval_with_full_metadata(self):
        @bridge_eval
        def my_eval(ctx: PipelineEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            assert ctx.metadata is not None
            assert ctx.metadata.branch == "main"
            assert ctx.metadata.pipeline_rid == "pid-1"
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        context_json = json.dumps({
            "pipeline_name": "test",
            "pipeline_input": {},
            "pipeline_output": {},
            "steps": {
                "step_a": {
                    "step_name": "step_a",
                    "input": "in_a",
                    "output": "out_a",
                    "trajectory": None,
                    "duration_ms": 100,
                    "success": True,
                },
                "step_b": {
                    "step_name": "step_b",
                    "input": "in_b",
                    "output": "out_b",
                    "trajectory": [{"event": "tool_call"}],
                    "duration_ms": 200,
                    "success": False,
                },
            },
            "metadata": {
                "pipeline_rid": "pid-1",
                "pipeline_version_id": "pv-1",
                "run_id": "run-1",
                "repository": "test-repo",
                "branch": "main",
                "commit_sha": "def456",
                "started_at": "2026-01-01T00:00:00",
                "completed_at": "2026-01-01T00:05:00",
                "duration_ms": 300000,
            },
        })

        result_json = await my_eval.on_invoke_eval(context=context_json)
        result = json.loads(result_json)
        assert result["metrics"]["accuracy"] == 1.0

    @pytest.mark.asyncio
    async def test_eval_with_nested_metrics(self):
        class NestedMetrics(TypedDict):
            scores: dict[str, float]
            tags: list[str]

        @bridge_eval
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[NestedMetrics]:
            return EvalResult(
                metrics={"scores": {"a": 1.0, "b": 0.5}, "tags": ["good", "fast"]},
            )

        context_json = json.dumps(
            {"step_name": "test", "step_input": None, "step_output": None, "metadata": {}}
        )

        result_json = await my_eval.on_invoke_eval(context=context_json)
        result = json.loads(result_json)
        assert result["metrics"]["scores"]["a"] == 1.0
        assert result["metrics"]["tags"] == ["good", "fast"]

    @pytest.mark.asyncio
    async def test_typed_step_context_deserialization(self):
        from pydantic import BaseModel

        class StepInput(BaseModel):
            expected: str

        class StepOutput(BaseModel):
            answer: str

        @bridge_eval
        def my_eval(
            ctx: StepEvalContext[StepInput, StepOutput],
        ) -> EvalResult[QualityMetrics]:
            return EvalResult(
                metrics={
                    "accuracy": 1.0 if ctx.step_output.answer == ctx.step_input.expected else 0.0,
                    "followed_format": True,
                }
            )

        context_json = json.dumps(
            {
                "step_name": "test",
                "step_input": {"expected": "right"},
                "step_output": {"answer": "right"},
                "metadata": {},
            }
        )

        result_json = await my_eval.on_invoke_eval(context=context_json)
        result = json.loads(result_json)
        assert result["metrics"]["accuracy"] == 1.0

    @pytest.mark.asyncio
    async def test_typed_pipeline_context_deserialization(self):
        from pydantic import BaseModel

        class PipelineInput(BaseModel):
            dataset: str

        class PipelineOutput(BaseModel):
            score: float

        @bridge_eval
        def my_eval(
            ctx: PipelineEvalContext[PipelineInput, PipelineOutput],
        ) -> EvalResult[QualityMetrics]:
            return EvalResult(
                metrics={
                    "accuracy": ctx.pipeline_output.score,
                    "followed_format": ctx.pipeline_input.dataset == "golden",
                }
            )

        context_json = json.dumps(
            {
                "pipeline_name": "test_pipeline",
                "pipeline_input": {"dataset": "golden"},
                "pipeline_output": {"score": 1.0},
                "steps": {},
            }
        )

        result_json = await my_eval.on_invoke_eval(context=context_json)
        result = json.loads(result_json)
        assert result["metrics"]["accuracy"] == 1.0
        assert result["metrics"]["followed_format"] is True

    @pytest.mark.asyncio
    async def test_step_eval_accepts_rfc3339_z_timestamps(self):
        @bridge_eval
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(
                metrics={
                    "accuracy": 1.0,
                    "followed_format": ctx.metadata.started_at.tzinfo is not None,
                }
            )

        context_json = json.dumps(
            {
                "step_name": "test_step",
                "step_input": None,
                "step_output": None,
                "metadata": {
                    "started_at": "2026-01-01T00:00:00.123456789Z",
                    "completed_at": "2026-01-01T00:01:00Z",
                },
            }
        )

        result_json = await my_eval.on_invoke_eval(context=context_json)
        result = json.loads(result_json)
        assert result["metrics"]["accuracy"] == 1.0
        assert result["metrics"]["followed_format"] is True


# --- Internal helper tests ---


class TestInternalHelpers:
    def test_build_step_context_with_partial_metadata(self):
        ctx = _build_step_eval_context({
            "step_name": "my_step",
            "step_input": {"key": "val"},
            "step_output": "result",
            "metadata": {"branch": "feature"},
        })
        assert ctx.step_name == "my_step"
        assert ctx.metadata.branch == "feature"
        assert ctx.metadata.step_rid == ""  # default for missing field
        assert ctx.metadata.duration_ms == 0

    def test_build_step_context_with_no_metadata_key(self):
        ctx = _build_step_eval_context({
            "step_name": "my_step",
            "step_input": None,
            "step_output": None,
        })
        assert ctx.metadata.branch == ""
        assert ctx.metadata.step_rid == ""

    def test_build_step_context_parses_rfc3339(self):
        ctx = _build_step_eval_context({
            "step_name": "my_step",
            "step_input": None,
            "step_output": None,
            "metadata": {
                "started_at": "2026-03-05T10:30:00.123456789Z",
                "completed_at": "2026-03-05T10:31:00Z",
            },
        })
        assert ctx.metadata.started_at.tzinfo is not None
        assert ctx.metadata.started_at.microsecond == 123456

    def test_build_pipeline_context_no_metadata(self):
        ctx = _build_pipeline_eval_context({
            "pipeline_name": "test",
            "pipeline_input": {},
            "pipeline_output": {},
        })
        assert ctx.metadata is None
        assert ctx.steps == {}

    def test_build_pipeline_context_multiple_steps(self):
        ctx = _build_pipeline_eval_context({
            "pipeline_name": "test",
            "pipeline_input": {},
            "pipeline_output": {},
            "steps": {
                "a": {"input": 1, "output": 2, "duration_ms": 10, "success": True},
                "b": {"input": 3, "output": 4, "duration_ms": 20, "success": False},
            },
        })
        assert len(ctx.steps) == 2
        assert ctx.steps["a"].output == 2
        assert ctx.steps["b"].success is False

    def test_serialize_eval_result_with_string_result(self):
        result = EvalResult(metrics={"score": 1.0}, result="reasoning")
        s = _serialize_eval_result(result)
        parsed = json.loads(s)
        assert parsed["metrics"]["score"] == 1.0
        assert parsed["result"] == {
            "type": "string",
            "string_value": "reasoning",
        }

    def test_serialize_eval_result_without_result(self):
        result = EvalResult(metrics={"score": 1.0})
        s = _serialize_eval_result(result)
        parsed = json.loads(s)
        assert "result" not in parsed

    def test_serialize_eval_result_with_boolean_result(self):
        result = EvalResult(metrics={"score": 1.0}, result=True)
        s = _serialize_eval_result(result)
        parsed = json.loads(s)
        assert parsed["result"] == {
            "type": "boolean",
            "boolean_value": True,
        }

    def test_serialize_eval_result_with_numeric_result(self):
        result = EvalResult(metrics={"score": 1.0}, result=0.42)
        s = _serialize_eval_result(result)
        parsed = json.loads(s)
        assert parsed["result"] == {
            "type": "number",
            "number_value": 0.42,
        }

    def test_serialize_eval_result_invalid_result_type_raises(self):
        with pytest.raises(ValidationError):
            EvalResult(metrics={"score": 1.0}, result=["bad"])  # type: ignore[arg-type]


# --- Type extraction edge cases ---


class TestTypeExtractionEdgeCases:
    def test_bare_step_eval_context_no_generics(self):
        """Using StepEvalContext without [I, O] should default to Any."""

        @bridge_eval
        def my_eval(ctx: StepEvalContext) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        assert my_eval.eval_data.context_type == "step"
        assert my_eval.eval_data.input_type_schema is None
        assert my_eval.eval_data.output_type_schema is None

    def test_bare_pipeline_eval_context_no_generics(self):
        @bridge_eval
        def my_eval(ctx: PipelineEvalContext) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        assert my_eval.eval_data.context_type == "pipeline"

    def test_bare_eval_result_no_generics(self):
        """EvalResult without [M] should produce empty metrics_schema."""

        @bridge_eval
        def my_eval(ctx: StepEvalContext) -> EvalResult:
            return EvalResult(metrics={})

        assert my_eval.eval_data.metrics_schema == {}

    def test_description_propagates(self):
        @bridge_eval(description="Checks quality")
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        assert my_eval.eval_data.description == "Checks quality"

    def test_metrics_schema_json_serializable(self):
        @bridge_eval
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        # Must not raise
        json.dumps(my_eval.eval_data.metrics_schema)


# --- Condition JSON serialization ---


class TestConditionJsonSerialization:
    def test_all_conditions_json_serializable(self):
        conditions = [
            always(),
            never(),
            on_branch("main"),
            sample(0.5),
            on_branch("main") & sample(0.1),
            on_branch("a") | on_branch("b"),
            (on_branch("main") & sample(0.1)) | always(),
        ]
        for c in conditions:
            serialized = json.dumps(c.to_cel())
            roundtripped = json.loads(serialized)
            assert roundtripped == c.to_cel()

    def test_and_inside_or_does_not_flatten(self):
        result = ((on_branch("a") & on_branch("b")) | on_branch("c")).to_cel()
        assert result == '((metadata.branch == "a") && (metadata.branch == "b")) || (metadata.branch == "c")'

    def test_or_inside_and_does_not_flatten(self):
        result = ((on_branch("a") | on_branch("b")) & on_branch("c")).to_cel()
        assert result == '((metadata.branch == "a") || (metadata.branch == "b")) && (metadata.branch == "c")'


# --- Pipeline and step integration ---


class TestPipelineEvalIntegration:
    def test_eval_bindings_on_pipeline_step(self):
        """eval_bindings should work with @pipeline.step too."""

        @bridge_eval
        def my_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        pipeline = Pipeline(name="test_pipeline")

        @pipeline.step(eval_bindings=[(my_eval, on_branch("main"))])
        def my_step(value: str) -> str:
            return value

        assert len(my_step.step_data.eval_bindings) == 1
        assert my_step.step_data.eval_bindings[0].eval_name == "my_eval"
        assert my_step.step_data.pipeline == "test_pipeline"

    def test_pipeline_constructor_multiple_bindings(self):
        @bridge_eval
        def eval_a(ctx: PipelineEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        @bridge_eval
        def eval_b(ctx: PipelineEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        pipeline = Pipeline(
            name="test_pipeline",
            eval_bindings=[
                (eval_a, on_branch("main")),
                (eval_b, sample(0.5)),
            ],
        )

        assert len(pipeline._eval_bindings) == 2
        names = {b.eval_name for b in pipeline._eval_bindings}
        assert names == {"eval_a", "eval_b"}

    def test_pipeline_constructor_invalid_eval_ref_type(self):
        with pytest.raises(TypeError, match="EvalFunction | str"):
            Pipeline(
                name="test_pipeline",
                eval_bindings=[(42, always())],  # type: ignore[list-item]
            )


# --- Full DSL roundtrip ---


class TestFullDSLRoundtrip:
    def test_complete_dsl_structure(self):
        """Verify the full DSL JSON structure matches the design doc contract."""

        @bridge_eval
        def quality_check(
            ctx: StepEvalContext[Any, Any],
        ) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        @bridge_eval
        def pipeline_eval(
            ctx: PipelineEvalContext[Any, Any],
        ) -> EvalResult[QualityMetrics]:
            return EvalResult(metrics={"accuracy": 1.0, "followed_format": True})

        pipeline = Pipeline(
            name="my_pipeline",
            description="Test pipeline",
            eval_bindings=[(pipeline_eval, always())],
        )

        @pipeline.step(
            eval_bindings=[
                (quality_check, on_branch("main")),
                ("llm_judge", on_branch("main") & sample(0.1)),
            ]
        )
        def my_step(value: str) -> str:
            return value

        # Build DSL output the same way cli.py does
        from bridge_sdk.pipeline import PipelineData

        steps_dict = {
            name: sf.step_data.model_dump()
            for name, sf in STEP_REGISTRY.items()
        }
        pipelines_dict = {
            pname: PipelineData(
                name=p.name,
                rid=p.rid,
                description=p.description,
                eval_bindings=p._eval_bindings,
            ).model_dump()
            for pname, p in PIPELINE_REGISTRY.items()
        }
        evals_dict = {
            name: ef.eval_data.model_dump()
            for name, ef in EVAL_REGISTRY.items()
        }

        dsl = {
            "steps": steps_dict,
            "pipelines": pipelines_dict,
            "evals": evals_dict,
        }

        # Verify JSON-serializable
        dsl_json = json.dumps(dsl, indent=2)
        parsed = json.loads(dsl_json)

        # Top-level keys
        assert set(parsed.keys()) == {"steps", "pipelines", "evals"}

        # Step with eval bindings
        assert "my_step" in parsed["steps"]
        step_data = parsed["steps"]["my_step"]
        assert step_data["pipeline"] == "my_pipeline"
        assert len(step_data["eval_bindings"]) == 2
        binding_names = {b["eval_name"] for b in step_data["eval_bindings"]}
        assert binding_names == {"quality_check", "llm_judge"}

        # Composite condition
        llm_binding = next(
            b for b in step_data["eval_bindings"] if b["eval_name"] == "llm_judge"
        )
        assert llm_binding["condition"] == "(metadata.branch == \"main\") && (sample_value < 0.1)"

        # Pipeline with eval bindings
        assert "my_pipeline" in parsed["pipelines"]
        pipe_data = parsed["pipelines"]["my_pipeline"]
        assert len(pipe_data["eval_bindings"]) == 1
        assert pipe_data["eval_bindings"][0]["eval_name"] == "pipeline_eval"

        # Evals
        assert "quality_check" in parsed["evals"]
        assert "pipeline_eval" in parsed["evals"]
        assert parsed["evals"]["quality_check"]["context_type"] == "step"
        assert parsed["evals"]["pipeline_eval"]["context_type"] == "pipeline"
        assert "metrics_schema" in parsed["evals"]["quality_check"]
