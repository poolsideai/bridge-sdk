# Bridge SDK

A Python SDK for defining workflow steps with dependency management.

## Quick Start

### 1. Create a new project

```bash
uv init my_project
cd my_project
uv add bridge-sdk@git+https://github.com/poolsideai/bridge-sdk.git@v0.1.0
```

### 2. Set up your project structure

```
my_project/
├── pyproject.toml
└── my_project/
    ├── __init__.py
    └── steps.py
```

### 3. Define your steps

Create `my_project/steps.py`:

```python
from typing import Annotated
from pydantic import BaseModel
from bridge_sdk import step, step_result

class ProcessInput(BaseModel):
    value: str

class ProcessOutput(BaseModel):
    result: str

@step
def process_data(input_data: ProcessInput) -> ProcessOutput:
    return ProcessOutput(result=f"processed: {input_data.value}")

@step
def transform_data(
    input_data: ProcessInput,
    previous: Annotated[ProcessOutput, step_result(process_data)],
) -> ProcessOutput:
    return ProcessOutput(result=f"{previous.result} -> {input_data.value}")
```

### 4. Configure Bridge SDK

Add to your `pyproject.toml`:

```toml
[tool.bridge]
modules = ["my_project.steps"]
```

> **Note:** Your project must have a `[build-system]` section (created by `uv init`) for modules to be importable.

### 5. Run

```bash
uv sync
uv run bridge check                    # Validate setup
uv run bridge config get-dsl           # Get step definitions
uv run bridge run --step process_data --input '{"input_data": {"value": "test"}}' --results '{}'
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `bridge check` | Validate project setup |
| `bridge config get-dsl` | Export step definitions as JSON |
| `bridge run --step <name> --input <json> --results <json>` | Execute a step |

### Options

**`config get-dsl`:**
- `--modules` - Override modules from config
- `--output-file` - Write output to file (default: `/tmp/config_get_dsl/dsl.json`)

**`run`:**
- `--step` - Step name (required)
- `--input` - Input JSON (required)
- `--results` - Cached results JSON from previous steps
- `--results-file` - Path to results JSON file
- `--output-file` - Write result to file

## Defining Steps

### Basic Step

```python
from bridge_sdk import step

@step
def my_step(value: str) -> str:
    return f"result: {value}"
```

### Step with Dependencies

Use `step_result` to declare dependencies:

```python
from typing import Annotated
from bridge_sdk import step, step_result

@step
def step_a() -> str:
    return "from step A"

@step
def step_b(dep: Annotated[str, step_result(step_a)]) -> str:
    return f"received: {dep}"
```

### Step Decorator Options

```python
@step(
    name="custom_name",                    # Override function name
    description="Does something useful",
    setup_script="setup.sh",
    post_execution_script="cleanup.sh",
    metadata={"type": "agent"},
    sandbox_id="my-sandbox",
)
def my_step() -> str:
    return "done"
```

### Async Steps

```python
@step
async def async_step(value: str) -> str:
    return f"async result: {value}"
```

## Calling Agents

```python
from bridge_sdk import step, step_result
from bridge_sdk.bridge_sidecar_client import BridgeSidecarClient
from bridge_sdk.proto.bridge_sidecar_pb2 import ContinueFrom, RunDetail

@step
def run_agent() -> dict:
    with BridgeSidecarClient() as client:
        _, session_id, result = client.start_agent(
            prompt="say hello",
            agent_name="my-agent"
        )
        return {"session_id": session_id, "result": result}
```

## API Reference

```python
from bridge_sdk import (
    step,           # Decorator for defining steps
    step_result,    # Annotation helper for step dependencies
    StepFunction,   # Type for decorated step functions
    StepData,       # Pydantic model for step metadata
    STEP_REGISTRY,  # Global registry of discovered steps
    get_dsl_output, # Generate DSL from registry
)

from bridge_sdk.bridge_sidecar_client import BridgeSidecarClient
from bridge_sdk.proto.bridge_sidecar_pb2 import ContinueFrom, RunDetail
```

## Development

```bash
make venv   # Create virtual environment
make sync   # Install dependencies
make proto  # Generate protocol buffers
make test   # Run tests
```
