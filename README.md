# Bridge SDK

A Python SDK for defining workflow steps with dependency management.

## Quick Start

### 1. Create a new project

```bash
uv init my_project
cd my_project
uv add bridge-sdk@git+https://github.com/poolsideai/bridge-sdk.git
```

### 2. Set up your project structure

Create the package directory and files:

```bash
mkdir -p my_project
touch my_project/__init__.py
```

Your project should look like this:

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

Add the following to your `pyproject.toml`:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.bridge]
modules = ["my_project.steps"]
```

> **Note:** The `[build-system]` section is required for your modules to be importable. Recent versions of `uv init` may not generate it by default.

Then sync to install your project in development mode:

```bash
uv sync
```

### 5. Set up `main.py`

The Bridge orchestrator expects a `main.py` at the root of your project that imports and runs the CLI:

```python
from bridge_sdk.cli import main

if __name__ == "__main__":
    main()
```

### 6. Run

To test locally, you can use the `uv run bridge` commands:

```bash
uv sync
uv run bridge check                    # Validate setup
uv run bridge config get-dsl           # Get step definitions
uv run bridge run --step process_data --input '{"input_data": {"value": "test"}}' --results '{}'
```

## Organizing Multiple Step Files

As your project grows, you may want to split steps across multiple files. There are two ways to set this up:

**Option A: List each module explicitly**

```
my_project/
├── pyproject.toml
└── my_project/
    └── steps/
        ├── __init__.py
        ├── ingestion.py
        └── transform.py
```

```toml
[tool.bridge]
modules = ["my_project.steps.ingestion", "my_project.steps.transform"]
```

This is the most explicit approach — each module is listed individually. If you forget to add a new module, you'll get a clear error rather than silent missing steps.

**Option B: Re-export from `__init__.py`**

Import all step modules from your package's `__init__.py` and point `tool.bridge` to the package:

```python
# my_project/steps/__init__.py
from .ingestion import *
from .transform import *
```

```toml
[tool.bridge]
modules = ["my_project.steps"]
```

This keeps your `tool.bridge` config short, but you must remember to update `__init__.py` whenever you add a new step file.

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

### Credential Bindings

Use `credential_bindings` to inject credentials from Bridge into your step's environment. The dictionary key is the **credential UUID** registered in Bridge, and the value is the **environment variable name** the credential will be exposed as at runtime.

```python
@step(
    credential_bindings={
        "a1b2c3d4-5678-90ab-cdef-1234567890ab": "MY_API_KEY",
        "f0e1d2c3-b4a5-6789-0abc-def123456789": "DB_PASSWORD",
    },
)
def my_step() -> str:
    import os
    api_key = os.environ["MY_API_KEY"]
    return f"authenticated"
```

### Async Steps

```python
@step
async def async_step(value: str) -> str:
    return f"async result: {value}"
```

## Calling Agents

The `BridgeSidecarClient.start_agent()` method returns a tuple of `(_, session_id, status)`, where `status` is just a success/fail message, **not** the actual agent output.

To get the agent's response, you must:
1. Instruct the agent in the prompt to write its output to a specific file
2. Read that file after the agent completes

```python
import json
from bridge_sdk import step
from bridge_sdk.bridge_sidecar_client import BridgeSidecarClient

OUTPUT_FILE = "/tmp/agent_output.json"

PROMPT = """Do some analysis and write your results.

CRITICAL: You MUST write your output to {output_file} using the write tool.

Output JSON structure:
{{
    "result": "your analysis here",
    "details": ["item1", "item2"]
}}
"""

@step
def run_agent() -> dict:
    prompt = PROMPT.format(output_file=OUTPUT_FILE)

    with BridgeSidecarClient() as client:
        _, session_id, _ = client.start_agent(
            prompt=prompt,
            agent_name="my-agent"
        )

    # Read the output from the file the agent wrote
    try:
        with open(OUTPUT_FILE, "r") as f:
            output_data = json.load(f)
        response = json.dumps(output_data, indent=2)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        response = f"Error reading output file: {e}"

    return {"session_id": session_id, "response": response}
```

### Continuing from a Previous Session

To continue an agent session (preserving context from a previous step):

```python
from bridge_sdk.bridge_sidecar_client import BridgeSidecarClient
from bridge_sdk.proto.bridge_sidecar_pb2 import ContinueFrom, RunDetail

with BridgeSidecarClient() as client:
    _, session_id, _ = client.start_agent(
        prompt=prompt,
        agent_name="my-agent",
        continue_from=ContinueFrom(
            previous_run_detail=RunDetail(
                agent_name="my-agent",
                session_id=previous_session_id,
            ),
            continuation=ContinueFrom.NoCompactionStrategy(),
        ),
    )
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

### Pre-commit Hooks

This project uses pre-commit hooks to automatically update `uv.lock` when `pyproject.toml` changes.

**Setup:**
```bash
uv sync
uv run pre-commit install
```

**What it does:**
- Automatically runs `uv lock` when you commit changes to `pyproject.toml`
- Ensures `uv.lock` is always in sync with dependencies
- Adds the updated `uv.lock` to your commit automatically

**Manual run:**
```bash
uv run pre-commit run --all-files
```
