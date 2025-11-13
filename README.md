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

## Usage

### Get DSL Configuration

Discover all steps in a module and retrieve their configuration:

```bash
python main.py config get-dsl --module examples
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
- `--module`: Module path to discover steps from (default: `examples`)

### More Examples

Run Step1 with no dependencies:
```bash
python main.py run --step Step1 --results '{}' --input "Initial data"
```

Run Step2 with Step1 result:
```bash
python main.py run --step Step2 --results '{"Step1": "transformed"}' --input "My input"
```

Get DSL from a custom module:
```bash
python main.py config get-dsl --module my_custom_module
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

## Project Structure

```
bridge_lib/
├── main.py              # CLI entry point
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
bridgecli config get-dsl --module examples

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
