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
pip install git+https://github.com/poolsideai/bridge-sdk.git
```

After installation, the `bridge` CLI command is automatically available.

## Quick Start

### 1. Create a step module

Create a file with your step definitions (e.g., `my_steps.py`):

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

### 2. Create a configuration file

Create `bridge_config.py` in your project root:

```python
STEP_MODULES = [
    "my_steps",
]
```

### 3. Run CLI commands

```bash
# Discover all steps and get their DSL configuration
bridge config get-dsl

# Run a specific step
bridge run --step process_data --input '{"input_data": {"value": "test"}}' --results '{}'
```

## CLI Reference

### Get DSL Configuration

Discover all steps and retrieve their configuration:

```bash
# Using config file (bridge_config.py)
bridge config get-dsl

# Specify modules directly
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
- `--modules`: Module paths to discover steps from (optional, uses `bridge_config.py` if not specified)
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
├── bridge_config.py             # Default module configuration
├── pyproject.toml
├── Makefile
└── README.md
```
