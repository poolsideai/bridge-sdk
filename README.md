# Bridge Library

A Python library and CLI for defining, discovering, and executing workflow steps with dependency management.

## Overview

Bridge Library allows you to define steps in your workflow using decorators. Each step can:
- Declare dependencies on other steps
- Accept inputs and results from previous steps
- Define setup and post-execution scripts
- Include custom metadata

The CLI provides commands to discover steps and execute them with dependency resolution.

## Installation

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Create virtual environment
make venv

# Sync dependencies
make sync

# Generate protocol buffers (if needed)
make proto
```

## Configuration

### Module Discovery

Specify which modules to scan for steps using one of these methods (in priority order):

1. **CLI arguments**: `--modules` (multiple module paths)
2. **Config file**: `bridge_config.py` with `STEP_MODULES` list

> **Note**: The `--module` (single) argument will be deprecated. Use `--modules` or configure `STEP_MODULES` in `bridge_config.py` instead.

Create a `bridge_config.py` in your project root:

```python
# bridge_config.py
STEP_MODULES = [
    "examples",
    "my_steps",
    "lib.custom_steps",
]
```

## Usage

### Get DSL Configuration

Discover all steps and retrieve their configuration:

```bash
# Using config file (bridge_config.py)
python main.py config get-dsl

# Multiple modules
python main.py config get-dsl --modules examples my_steps lib.custom_steps
```

This outputs the DSL representation of all discovered steps, including their dependencies, metadata, and scripts.

### Run a Specific Step

Execute a step with input and cached results from previous steps:

```bash
python main.py run --step Step3 --results '{"Step2": "Hello world"}' --input "Yours"
```

**Parameters:**
- `--step`: Name of the step to execute (required)
- `--results`: JSON object containing cached results from previous steps (required)
- `--input`: Input data for the step (required)
- `--modules`: Module paths to discover steps from (optional)
- `--module`: *(deprecated)* Single module path (optional)

If no module arguments are provided, modules are loaded from `bridge_config.py`.

### More Examples

Run Step1 with no dependencies:
```bash
python main.py run --step Step1 --results '{}' --input "Initial data"
```

Run Step2 with Step1 result:
```bash
python main.py run --step Step2 --results '{"Step1": "transformed"}' --input "My input"
```

Get DSL from multiple modules:
```bash
python main.py config get-dsl --modules examples plugins
```

## Defining Steps

Steps are defined using the `@step` decorator:

```python
from enum import Enum
from typing import Annotated
from lib import step, step_result, STEP_INPUT

class Steps(Enum):
    STEP_1 = "Step1"
    STEP_2 = "Step2"

@step(
    name=Steps.STEP_1.value,
    setup_script="setup.sh",
    post_execution_script="cleanup.sh",
    metadata={"type": "agent"},
    depends_on=[]
)
def step_1(input_data: Annotated[str, STEP_INPUT]) -> str:
    return f"processed: {input_data}"

@step(
    name=Steps.STEP_2.value,
    setup_script="setup.sh",
    post_execution_script="cleanup.sh",
    metadata={"type": "agent"},
    depends_on=[Steps.STEP_1.value]
)
def step_2(
    input_data: Annotated[str, STEP_INPUT],
    step_1_result: Annotated[str, step_result(Steps.STEP_1.value)]
) -> str:
    return f"{input_data} + {step_1_result}"
```

### Step Decorator Parameters

- `name`: Unique identifier for the step
- `setup_script`: Script to run before step execution (optional)
- `post_execution_script`: Script to run after step execution (optional)
- `metadata`: Custom metadata dictionary (optional)
- `execution_env`: Environment for execution such as container image (optional)
- `depends_on`: List of step names this step depends on (optional)

### Function Annotations

- `Annotated[type, STEP_INPUT]`: Marks a parameter as the step input
- `Annotated[type, step_result(step_name)]`: Injects the result from a previous step

## Calling Agents

The Bridge Library supports calling agents through the `BridgeSidecarClient`. To use agents, you need to have both the **sidecar** and **core API** running.

### Prerequisites

Make sure both services are running before calling agents:
- **Sidecar**: The Bridge sidecar service must be active
- **Core API**: The agent API service must be running

### Using Pydantic Types

You can use Pydantic `BaseModel` classes for both inputs and outputs, enabling type-safe data validation and structured results. This is particularly useful when chaining agents together or when you need to pass complex data structures between steps.

### Example: Agent with Pydantic Types

Here's a complete example (from `examples/agent_example.py`) showing how to call agents and use Pydantic models:

```python
from enum import Enum
from typing import Annotated, Optional
from pydantic import BaseModel

from lib import step, step_result, STEP_INPUT
from lib.bridge_sidecar_client import BridgeSidecarClient
from proto.bridge_sidecar_pb2 import ContinueFrom, RunDetail

class AgentSteps(Enum):
    HELLO_WORLD_AGENT = "HelloWorld"
    CONTINUATION_AGENT = "Continuation"

# Define a Pydantic model for the agent result
class HelloWorldResult(BaseModel):
    session_id: str
    res: str

@step(
    name=AgentSteps.HELLO_WORLD_AGENT.value,
    metadata={"type": "agent"},
    depends_on=[]
)
def hello_world_agent() -> HelloWorldResult:
    with BridgeSidecarClient() as client:
        _, session_id, res = client.start_agent(
            "say hello",
            agent_name="agent_1003_cc_v2_rc-fp8-tpr"
        )
        return HelloWorldResult(session_id=session_id, res=res)

# Define a Pydantic model for the continuation input
class ContinuationInput(BaseModel):
    prompt: str

@step(
    name=AgentSteps.CONTINUATION_AGENT.value,
    metadata={"type": "agent"},
    depends_on=[AgentSteps.HELLO_WORLD_AGENT.value]
)
def continuation_agent(
    input: Annotated[ContinuationInput, STEP_INPUT],
    prev_result: Annotated[HelloWorldResult, step_result(AgentSteps.HELLO_WORLD_AGENT.value)]
) -> Optional[str]:
    with BridgeSidecarClient() as client:
        _, session_id, res = client.start_agent(
            "tell me what was done previously",
            agent_name="agent_1003_cc_v2_rc-fp8-tpr",
            continue_from=ContinueFrom(
                previous_run_detail=RunDetail(
                    agent_name="agent_1003_cc_v2_rc-fp8-tpr",
                    session_id=prev_result.session_id
                ),
                continuation=ContinueFrom.NoCompactionStrategy()
            )
        )
        return session_id
```

### Key Features

- **Pydantic Models**: Use `BaseModel` for type-safe inputs and outputs
- **Session Management**: Access `session_id` from previous agent runs for continuations
- **Agent Chaining**: Pass results from one agent to another using `step_result()`
- **Context Manager**: Use `BridgeSidecarClient()` as a context manager for automatic cleanup

## Project Structure

```
bridge_lib/
├── main.py              # CLI entry point
├── bridge_config.py     # Module discovery configuration
├── lib/
│   ├── __init__.py
│   ├── step.py          # Step decorator and registry
│   ├── agent.py
│   └── grpc_client.py
├── examples/
│   ├── __init__.py
│   └── example.py       # Example step definitions
├── proto/
│   ├── bridge.proto
│   ├── bridge_pb2.py
│   └── bridge_pb2_grpc.py
├── Makefile
└── pyproject.toml
```

## Creating a CLI Alias (Optional)

To make the CLI easier to use, you can create an alias called `bridgecli`:

### Bash/Zsh

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
alias bridgecli='python $HOME/path/to/bridge_lib/main.py'
```

Then reload your shell:
```bash
source ~/.bashrc  # or source ~/.zshrc
```

### Usage with Alias

Once the alias is set up, you can use `bridgecli` instead of `python main.py`:

```bash
# Get DSL configuration
bridgecli config get-dsl --modules examples

# Run a step
bridgecli run --step Step3 --results '{"Step2": "Hello world"}' --input "Yours"
```

### Making it a Proper Command

For a more permanent solution, you can create a shell script:

```bash
#!/bin/bash
# Save as /usr/local/bin/bridgecli
python $HOME/path/to/bridge_lib/main.py "$@"
```

Make it executable:
```bash
chmod +x /usr/local/bin/bridgecli
```
