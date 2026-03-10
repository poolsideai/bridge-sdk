# Bridge Evals Reference

Evals are quality measurement functions that automatically run when steps or pipelines complete. They produce structured metrics that are tracked over time to detect regressions.

## Defining Evals

Use `@bridge_eval` to define an eval function. The function must:
1. Accept a `StepEvalContext` or `PipelineEvalContext` as its first parameter
2. Return an `EvalResult[M]` where `M` is a `TypedDict` defining the metrics schema

```python
from typing import TypedDict, Any
from bridge_sdk import bridge_eval, EvalResult, StepEvalContext

class QualityMetrics(TypedDict):
    accuracy: float
    followed_format: bool

@bridge_eval
def quality_check(ctx: StepEvalContext[Any, Any]) -> EvalResult[QualityMetrics]:
    is_correct = ctx.step_output.answer == ctx.step_input.expected
    return EvalResult(
        metrics={"accuracy": 1.0 if is_correct else 0.0, "followed_format": True},
        result="Optional reasoning text"
    )
```

### Decorator Options

```python
@bridge_eval                           # no parentheses
@bridge_eval()                         # empty parentheses
@bridge_eval(
    name="custom_name",                # override function name
    rid="550e8400-...",                # stable UUID across renames
    description="Checks output quality",
)
```

### Context Types

The first parameter's type determines what the eval targets:

**Step eval** — receives the step's input, output, and trajectory:

```python
@bridge_eval
def my_eval(ctx: StepEvalContext[InputType, OutputType]) -> EvalResult[M]:
    ctx.step_name        # str — name of the step
    ctx.step_input       # InputType — what was passed to the step
    ctx.step_output      # OutputType — what the step returned
    ctx.trajectory       # Any | None — agent trajectory for agentic steps
    ctx.metadata         # StepMetadata — rid, branch, timing, etc.
```

**Pipeline eval** — receives all step results:

```python
@bridge_eval
def my_eval(ctx: PipelineEvalContext[InputType, OutputType]) -> EvalResult[M]:
    ctx.pipeline_name    # str
    ctx.pipeline_input   # InputType
    ctx.pipeline_output  # OutputType
    ctx.steps            # dict[str, StepResult] — keyed by step name
    ctx.metadata         # PipelineMetadata | None
```

Access individual step results by name:

```python
@bridge_eval
def pipeline_eval(ctx: PipelineEvalContext[Any, Any]) -> EvalResult[M]:
    inference = ctx.steps["run_inference"]
    inference.output      # Any — step output
    inference.input       # Any — step input
    inference.trajectory  # Any | None
    inference.duration_ms # int
    inference.success     # bool
```

### Type Safety Levels

```python
# Exact types — only binds to steps with matching I/O types
@bridge_eval
def typed_eval(ctx: StepEvalContext[FraudInput, FraudOutput]) -> EvalResult[M]: ...

# Any types — binds to any step (generic/reusable evals)
@bridge_eval
def generic_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[M]: ...

# Bare context (no generics) — equivalent to Any
@bridge_eval
def bare_eval(ctx: StepEvalContext) -> EvalResult[M]: ...
```

### EvalResult

```python
from bridge_sdk import EvalResult

# Metrics are structured (TypedDict) — tracked quantitatively over time
# Result is optional typed output (`str`, `bool`, or `number`)
result = EvalResult(
    metrics={"accuracy": 0.95, "relevance": 4},
    result="The response was accurate but verbose..."
)
```

### Async Evals

```python
@bridge_eval
async def async_eval(ctx: StepEvalContext[Any, Any]) -> EvalResult[M]:
    result = await call_llm_judge(ctx.step_output)
    return EvalResult(metrics={"score": result.score}, result=result.reasoning)
```

## Binding Evals

### To Steps

Bind evals on `@step` using `eval_bindings`:

```python
from bridge_sdk import step, on_branch, sample

@step(
    eval_bindings=[
        (quality_check, on_branch("main")),
        (llm_judge, on_branch("main") & sample(0.1)),
    ]
)
def my_step(input: TaskInput) -> TaskOutput:
    ...
```

Works with `@pipeline.step` too:

```python
@pipeline.step(eval_bindings=[quality_check])
def my_step(value: str) -> str:
    ...
```

Each `eval_bindings` entry can be:
- `EvalFunction | str` (defaults condition to `true`)
- `(EvalFunction | str, Condition | str)`

### To Pipelines

Pipeline bindings are specified in the constructor as `(eval, condition)` tuples:

```python
from bridge_sdk import Pipeline, always

pipeline = Pipeline(
    name="my_pipeline",
    eval_bindings=[
        (pipeline_quality, always()),
        (llm_judge, on_branch("main") & sample(0.1)),
    ],
)
```

### Cross-repo References

Use a string name to reference evals defined in another repository:

```python
@step(eval_bindings=[("other_repo/quality_check", always())])
def my_step(value: str) -> str:
    ...
```

## Conditions

Conditions control when an eval runs. They are evaluated by the platform before execution.

| Factory | CEL serialization | Description |
|---------|-------------------|-------------|
| `always()` | `true` | Every execution (default) |
| `never()` | `false` | Never run |
| `on_branch("main")` | `metadata.branch == "main"` | Only on specified branch |
| `sample(0.1)` | `sample_value < 0.1` | Deterministic 10% of executions |

### Combinators

```python
on_branch("main") & sample(0.1)           # AND — both must pass
on_branch("main") | on_branch("staging")   # OR — either passes
(on_branch("main") & sample(0.1)) | always()  # Nested
```

## DSL Output

`bridge config get-dsl` includes evals in the JSON output:

```json
{
  "steps": {
    "my_step": {
      "name": "my_step",
      "eval_bindings": [
        {
          "eval_name": "quality_check",
          "condition": "metadata.branch == \"main\""
        }
      ]
    }
  },
  "pipelines": {
    "my_pipeline": {
      "name": "my_pipeline",
      "eval_bindings": [
        {"eval_name": "pipeline_quality", "condition": "true"}
      ]
    }
  },
  "evals": {
    "quality_check": {
      "name": "quality_check",
      "context_type": "step",
      "file_path": "my_project/evals.py",
      "file_line_number": 10,
      "metrics_schema": {
        "type": "object",
        "properties": {
          "accuracy": {"type": "number"},
          "followed_format": {"type": "boolean"}
        },
        "required": ["accuracy", "followed_format"]
      },
      "input_type_schema": null,
      "output_type_schema": null
    }
  }
}
```

## Metadata Types

### StepMetadata

Available via `ctx.metadata` in step evals:

| Field | Type |
|-------|------|
| `step_rid` | `str` |
| `step_version_id` | `str` |
| `execution_id` | `str` |
| `repository` | `str` |
| `branch` | `str` |
| `commit_sha` | `str` |
| `started_at` | `datetime` |
| `completed_at` | `datetime` |
| `duration_ms` | `int` |

### PipelineMetadata

Available via `ctx.metadata` in pipeline evals:

| Field | Type |
|-------|------|
| `pipeline_rid` | `str` |
| `pipeline_version_id` | `str` |
| `run_id` | `str` |
| `repository` | `str` |
| `branch` | `str` |
| `commit_sha` | `str` |
| `started_at` | `datetime` |
| `completed_at` | `datetime` |
| `duration_ms` | `int` |
