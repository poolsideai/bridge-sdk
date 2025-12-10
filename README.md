# Bridge SDK

A Python SDK and CLI for defining, discovering, and executing workflow steps with dependency management.

## Overview

Bridge SDK allows you to define steps in your workflow using decorators. Each step can:
- Declare dependencies on other steps
- Accept inputs and results from previous steps
- Define setup and post-execution scripts
- Include custom metadata

The CLI provides commands to discover steps and execute them with dependency resolution.

## Installation

Install directly from the git repository:

```bash
# Install latest version
pip install git+https://github.com/poolsideai/bridge-sdk.git

# Install a specific version (recommended for production)
pip install git+https://github.com/poolsideai/bridge-sdk.git@v0.1.0
```

Or add to your `requirements.txt`:

```
bridge-sdk @ git+https://github.com/poolsideai/bridge-sdk.git@v0.1.0
```

Or in `pyproject.toml`:

```toml
[project]
dependencies = [
    "bridge-sdk @ git+https://github.com/poolsideai/bridge-sdk.git@v0.1.0",
]
```

### Running the CLI

After installation, how you invoke the `bridge` CLI depends on your environment:

```bash
# If using a virtual environment (activate it first)
source .venv/bin/activate
bridge --help

# If using uv
uv run bridge --help

# If using poetry
poetry run bridge --help

# Alternative: invoke as a Python module (works in any setup)
python -m bridge_sdk.cli --help
```

> **Note:** The `bridge` command is installed into your Python environment's `bin/` directory. If the command isn't found, ensure your virtual environment is activated or use `python -m bridge_sdk.cli` instead.

## Quick Start

### 1. Set up your project structure

Your project must be a proper Python package with a `[build-system]` in `pyproject.toml`:

```
my_project/
├── pyproject.toml
└── my_project/
    ├── __init__.py
    └── steps.py      # Your step definitions
```

### 2. Create your step definitions

Create your step module (e.g., `my_project/steps.py`):

```python
from typing import Annotated
from pydantic import BaseModel
from bridge_sdk import step, step_result

class ProcessInput(BaseModel):
    value: str

class ProcessOutput(BaseModel):
    result: str

@step(name="process_data")
def process_data(input_data: ProcessInput) -> ProcessOutput:
    return ProcessOutput(result=f"processed: {input_data.value}")

@step(name="transform_data")
def transform_data(
    input_data: ProcessInput,
    previous: Annotated[ProcessOutput, step_result("process_data")],
) -> ProcessOutput:
    return ProcessOutput(result=f"{previous.result} -> {input_data.value}")
```

### 3. Configure your project

Your `pyproject.toml` should include:

```toml
[project]
name = "my-project"
version = "0.1.0"
dependencies = [
    "bridge-sdk @ git+https://github.com/poolsideai/bridge-sdk.git@v0.1.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.bridge]
modules = ["my_project.steps"]
```

> **Important:** The `[build-system]` section is required so that your project gets installed and your step modules become importable.

### 4. Install and run

```bash
# Install dependencies (this also installs your project)
uv sync  # or: pip install -e .

# Discover all steps and get their DSL configuration
uv run bridge config get-dsl

# Run a specific step
uv run bridge run --step process_data --input '{"input_data": {"value": "test"}}' --results '{}'
```

## CLI Reference

### Check Project Setup

Validate that your project is correctly configured for Bridge SDK:

```bash
bridge check
```

This command verifies:
- `pyproject.toml` exists
- `[build-system]` section is configured (required for installation)
- `[tool.bridge]` section with modules list
- All configured modules are importable
- Steps are discovered and registered

Example output:
```
Checking Bridge SDK project setup...

[OK]   pyproject.toml exists
[OK]   [build-system] section configured
[OK]   [tool.bridge] section configured
[OK]   [tool.bridge.modules] configured: ['my_project.steps']

Checking module imports...
[OK]   Can import 'my_project.steps'

[OK]   Found 2 step(s):
       - process_data
       - transform_data

--------------------------------------------------

All checks passed! Your project is ready for Bridge SDK.
```

### Get DSL Configuration

Discover all steps and retrieve their configuration:

```bash
# Using config from pyproject.toml
bridge config get-dsl

# Or specify modules directly
bridge config get-dsl --modules my_steps other_module

# Write output to a specific file
bridge config get-dsl --output-file ./output/dsl.json
```

### Run a Step

Execute a step with input and cached results from previous steps:

```bash
bridge run --step <step_name> --input '<json>' --results '<json>'
```

**Parameters:**
- `--step`: Name of the step to execute (required)
- `--input`: JSON string of input data (required)
- `--results`: JSON object containing cached results from previous steps
- `--results-file`: Path to JSON file containing cached results (alternative to `--results`)
- `--modules`: Module paths to discover steps from (optional, uses `pyproject.toml` config if not specified)
- `--output-file`: Path to write the step result (optional)

**Examples:**

```bash
# Run a step with no dependencies
bridge run --step process_data --input '{"input_data": {"value": "hello"}}' --results '{}'

# Run a step that depends on previous results
bridge run --step transform_data \
  --input '{"input_data": {"value": "world"}}' \
  --results '{"process_data": {"result": "processed: hello"}}'

# Use a results file instead of inline JSON
bridge run --step transform_data \
  --input '{"input_data": {"value": "world"}}' \
  --results-file ./cached_results.json
```

## Defining Steps

### Basic Step

```python
from bridge_sdk import step

@step(name="my_step")
def my_step(value: str) -> str:
    return f"result: {value}"
```

### Step with Pydantic Models

```python
from pydantic import BaseModel
from bridge_sdk import step

class Input(BaseModel):
    value: str

class Output(BaseModel):
    result: str

@step(name="typed_step")
def typed_step(input_data: Input) -> Output:
    return Output(result=input_data.value)
```

### Step with Dependencies

Use `step_result` to declare dependencies on other steps:

```python
from typing import Annotated
from bridge_sdk import step, step_result

@step(name="step_a")
def step_a() -> str:
    return "from step A"

@step(name="step_b")
def step_b(
    dep: Annotated[str, step_result("step_a")],
) -> str:
    return f"received: {dep}"

# You can also reference step functions directly
@step(name="step_c")
def step_c(
    dep: Annotated[str, step_result(step_a)],
) -> str:
    return f"received: {dep}"
```

### Step Decorator Parameters

```python
@step(
    name="my_step",                        # Step name (defaults to function name)
    description="Does something useful",   # Optional description
    setup_script="setup.sh",               # Script to run before execution
    post_execution_script="cleanup.sh",    # Script to run after execution
    metadata={"type": "agent"},            # Custom metadata
    sandbox_id="my-sandbox",               # Execution environment ID
)
def my_step() -> str:
    return "done"
```

### Async Steps

Async functions are fully supported:

```python
from bridge_sdk import step

@step(name="async_step")
async def async_step(value: str) -> str:
    # Perform async operations
    return f"async result: {value}"
```

## Calling Agents

The SDK supports calling agents through `BridgeSidecarClient`. This requires the sidecar and core API services to be running.

```python
from typing import Annotated, Optional
from pydantic import BaseModel
from bridge_sdk import step, step_result
from bridge_sdk.bridge_sidecar_client import BridgeSidecarClient
from bridge_sdk.proto.bridge_sidecar_pb2 import ContinueFrom, RunDetail

class AgentResult(BaseModel):
    session_id: str
    result: str

@step(name="run_agent")
def run_agent() -> AgentResult:
    with BridgeSidecarClient() as client:
        _, session_id, result = client.start_agent(
            prompt="say hello",
            agent_name="agent_1003_cc_v2_rc-fp8-tpr"
        )
        return AgentResult(session_id=session_id, result=result)

@step(name="continue_agent")
def continue_agent(
    prev: Annotated[AgentResult, step_result("run_agent")],
) -> Optional[str]:
    with BridgeSidecarClient() as client:
        _, session_id, _ = client.start_agent(
            prompt="continue the conversation",
            agent_name="agent_1003_cc_v2_rc-fp8-tpr",
            continue_from=ContinueFrom(
                previous_run_detail=RunDetail(
                    agent_name="agent_1003_cc_v2_rc-fp8-tpr",
                    session_id=prev.session_id,
                ),
                continuation=ContinueFrom.NoCompactionStrategy(),
            ),
        )
        return session_id
```

## API Reference

### Imports

```python
from bridge_sdk import (
    step,           # Decorator for defining steps
    step_result,    # Annotation helper for step dependencies
    StepFunction,   # Type for decorated step functions
    StepData,       # Pydantic model for step metadata
    STEP_REGISTRY,  # Global registry of all discovered steps
    get_dsl_output, # Function to generate DSL from registry
)

from bridge_sdk.bridge_sidecar_client import BridgeSidecarClient
from bridge_sdk.proto.bridge_sidecar_pb2 import ContinueFrom, RunDetail
```

## Development

### Setup

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Create virtual environment
make venv

# Sync dependencies
make sync

# Generate protocol buffers (if needed)
make proto

# Run tests
make test
```

### Project Structure

```
bridge-sdk/
├── bridge_sdk/
│   ├── __init__.py              # Public API exports
│   ├── cli.py                   # CLI entry point
│   ├── step.py                  # Step decorator and registry
│   ├── step_data.py             # StepData model
│   ├── annotations.py           # step_result helper
│   ├── function_schema.py       # Function schema extraction
│   ├── bridge_sidecar_client.py # gRPC client for agents
│   ├── exceptions.py            # Custom exceptions
│   ├── logger.py                # Logging configuration
│   ├── utils.py                 # Utility functions
│   └── proto/                   # Protocol buffer definitions
│       ├── bridge_sidecar.proto
│       ├── bridge_sidecar_pb2.py
│       └── bridge_sidecar_pb2_grpc.py
├── examples/                    # Example step definitions
├── tests/                       # Test suite
├── pyproject.toml
├── Makefile
└── README.md
```
