---
name: bridge-pipelines
description: >
  Build and configure Bridge pipelines using the Bridge SDK. Use when the task involves
  creating pipeline steps, defining step dependencies (DAGs), integrating agents into
  pipelines, configuring credential bindings, setting up pyproject.toml for Bridge,
  or working with the Bridge CLI (bridge check, bridge config get-dsl, bridge run).
  Also use when connecting pipelines to the Poolside web interface via repository
  indexing and build execution.
---

# Bridge Pipelines

Bridge is a workflow orchestration framework for defining and executing multi-step
data processing pipelines with automatic dependency management. Pipelines are defined
in Python using the Bridge SDK, stored in a git repository, and executed via the
Poolside web interface.

## End-to-End Flow

1. Define pipeline steps in Python using the Bridge SDK
2. Configure `pyproject.toml` with `[tool.bridge]` section
3. Push code to a git repository
4. Register the repository in the Poolside web interface (Bridge UI)
5. Index a commit — the system runs SDK analysis to discover pipelines and steps
6. Create a build to execute the pipeline DAG

## Quick Start

### Project Setup

```bash
uv init my_project
cd my_project
uv add bridge-sdk@git+https://github.com/poolsideai/bridge-sdk.git
```

### Configure pyproject.toml

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.bridge]
modules = ["my_project.steps"]
```

The `modules` list tells Bridge which Python modules to import when discovering steps.

### Define a Pipeline

```python
# my_project/steps.py
from typing import Annotated
from pydantic import BaseModel
from bridge_sdk import Pipeline, step_result

pipeline = Pipeline(
    name="my_pipeline",
    rid="550e8400-e29b-41d4-a716-446655440000",  # optional stable ID
    description="My processing pipeline",
)

class InputData(BaseModel):
    value: str

class ProcessedData(BaseModel):
    result: str

@pipeline.step
def ingest() -> InputData:
    return InputData(value="raw data")

@pipeline.step
def process(data: Annotated[InputData, step_result(ingest)]) -> ProcessedData:
    return ProcessedData(result=f"processed: {data.value}")
```

### Validate and Test

```bash
uv run bridge check          # Validate project setup
uv run bridge config get-dsl # Generate DSL (shows discovered steps/pipelines)
uv run bridge run --step ingest --input '{}' --results '{}'
```

## Core Concepts

### Pipeline

A named container grouping related steps. Auto-registers on instantiation.

```python
pipeline = Pipeline(
    name="my_pipeline",
    rid="uuid-here",       # optional — stable identity across renames
    description="...",
)
```

### Steps

Steps are the execution units. Use `@pipeline.step` to bind a step to a pipeline.

```python
@pipeline.step(
    name="custom_name",                   # override function name
    rid="uuid-here",                      # stable resource ID
    description="What this step does",
    setup_script="scripts/setup.sh",      # runs before step
    post_execution_script="scripts/cleanup.sh",  # runs after step
    metadata={"type": "agent"},           # arbitrary metadata
    credential_bindings={                 # credential UUID → env var
        "cred-uuid": "API_KEY",
    },
)
def my_step(input_data: InputModel) -> OutputModel:
    ...
```

All parameters and return types must be JSON-serializable (Pydantic models, primitives, collections, dataclasses, enums, Optional, Union).

The decorator supports multiple invocation styles:

```python
@pipeline.step            # no parentheses
@pipeline.step()          # empty parentheses
@pipeline.step(name="x")  # with arguments
```

### Step Dependencies (DAG)

Declare dependencies using `step_result` annotations. The DAG is automatically inferred.

```python
from typing import Annotated
from bridge_sdk import step_result

@pipeline.step
def upstream() -> DataModel:
    return DataModel(...)

@pipeline.step
def downstream(
    data: Annotated[DataModel, step_result(upstream)],
    other: Annotated[OtherModel, step_result(another_step)],
) -> ResultModel:
    # data is automatically populated from upstream's output
    return ResultModel(...)
```

A step can depend on multiple upstream steps. Steps with no dependencies run first. The orchestrator executes steps in parallel when their dependencies are satisfied.

### Credential Bindings

Inject credentials as environment variables at runtime:

```python
@pipeline.step(
    credential_bindings={
        "a1b2c3d4-5678-90ab-cdef-1234567890ab": "MY_API_KEY",
        "f0e1d2c3-b4a5-6789-0abc-def123456789": "DB_PASSWORD",
    }
)
def secure_step() -> str:
    import os
    api_key = os.environ["MY_API_KEY"]
    return "done"
```

Keys are credential UUIDs registered in the Bridge UI. Values are the env var names to inject.

### Webhooks

Pipelines can be triggered by external webhook events. Define webhooks in the pipeline code — they are discovered during indexing and start disabled until configured via the UI.

```python
from bridge_sdk import Pipeline, Webhook, WebhookProvider

pipeline = Pipeline(
    name="on_issue_update",
    webhooks=[
        Webhook(
            branch="main",
            filter='payload.type == "Issue" && payload.action == "update"',
            name="linear-issues",
            provider=WebhookProvider.LINEAR,
            transform='{"triage_step": {"issue_id": payload.data.id, "title": payload.data.title}}',
        ),
        Webhook(
            branch="main",
            filter='payload.ref == "refs/heads/main"',
            name="github-push",
            provider=WebhookProvider.GITHUB,
            transform='{"index_step": {"repo": payload.repository.full_name, "commit_sha": payload.head_commit.id}}',
        ),
    ],
)
```

**Webhook fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `branch` | `str` | Yes | The git branch this webhook applies to |
| `filter` | `str` | Yes | CEL expression returning `bool` — webhook fires only when true |
| `idempotency_key` | `str` | Conditional | CEL expression returning `string` for deduplication. Required for generic providers, forbidden for named providers. |
| `name` | `str` | Yes | Unique name within the pipeline + branch |
| `provider` | `str` | Yes | Provider identifier (use `WebhookProvider` constants) |
| `transform` | `str` | Yes | CEL expression returning `map(string, dyn)` — step name to input map |

**Available providers:** `github`, `gitlab`, `grafana`, `linear`, `slack`, `stripe`, `generic_hmac_sha1`, `generic_hmac_sha256`

CEL expressions receive `payload` (the parsed JSON body) and `headers` (HTTP headers as `map(string, string)`).

## Agent Integration

Steps can launch AI agents via the Bridge sidecar gRPC service. See [references/agents.md](references/agents.md) for the full agent integration guide.

```python
from bridge_sdk.bridge_sidecar_client import BridgeSidecarClient

@pipeline.step(metadata={"type": "agent"})
def agent_step() -> dict:
    output_file = "/tmp/agent_output.json"
    with BridgeSidecarClient() as client:
        _, session_id, _ = client.start_agent(
            prompt=f"Analyze data and write results to {output_file}",
            agent_name="Malibu",
        )
    with open(output_file) as f:
        return json.load(f)
```

**Important:** `start_agent()` returns `(agent_name, session_id, exit_result)`. The `exit_result` is just a status message — not the agent's output. Agents must write results to a file that the step reads.

## CLI Reference

| Command | Purpose |
|---------|---------|
| `bridge check` | Validate pyproject.toml and discover steps |
| `bridge config get-dsl` | Generate JSON DSL of all pipelines and steps |
| `bridge run --step NAME --input JSON --results JSON` | Execute a single step locally |

See [references/cli.md](references/cli.md) for full CLI details.

## Web Interface Integration

See [references/web-integration.md](references/web-integration.md) for how pipelines connect to the Poolside web interface, including repository management, commit indexing, build execution, and the API.
