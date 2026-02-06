# Bridge SDK - Agent Instructions

## Project Overview

Bridge SDK is a Python SDK for defining workflow pipelines with automatic dependency
management. Pipelines are defined using `@pipeline.step` decorators and `step_result`
annotations, then executed by the Bridge orchestrator on the Poolside platform.

## Development

```bash
make venv   # Create virtual environment
make sync   # Install dependencies
make proto  # Generate protocol buffers
make test   # Run tests
```

Pre-commit hooks are configured — run `uv run pre-commit install` after cloning.

## Key Architecture

- `bridge_sdk/pipeline.py` — Pipeline class and PIPELINE_REGISTRY
- `bridge_sdk/step.py` — `@step` decorator (deprecated) and `get_dsl_output()`
- `bridge_sdk/step_function.py` — StepFunction wrapper and STEP_REGISTRY
- `bridge_sdk/step_data.py` — StepData Pydantic model
- `bridge_sdk/annotations.py` — `step_result()` annotation helper
- `bridge_sdk/function_schema.py` — JSON schema generation from function signatures
- `bridge_sdk/cli.py` — CLI commands: `check`, `config get-dsl`, `run`
- `bridge_sdk/bridge_sidecar_client.py` — gRPC client for agent integration
- `bridge_sdk/proto/bridge_sidecar.proto` — gRPC service definition
- `examples/` — Example pipelines (agent_example.py, example.py)
- `tests/` — Test suite

## Downstream Skill: bridge-pipelines

There is a **bridge-pipelines** skill in the
[agent-toolkit](https://github.com/poolsideai/agent-toolkit) repository
(path: `bridge-pipelines/`) that teaches agents how to build Bridge pipelines.

**When making changes that affect how the SDK is used** — such as changes to the
public API, decorators, annotations, CLI commands, agent integration, configuration
format, or usage patterns — **you must also create a PR in the agent-toolkit repo**
to update the bridge-pipelines skill so it stays in sync.

The skill files to update:
- `bridge-pipelines/SKILL.md` — Core usage guide (quick start, concepts, examples)
- `bridge-pipelines/references/agents.md` — Agent integration via BridgeSidecarClient
- `bridge-pipelines/references/cli.md` — CLI command reference
- `bridge-pipelines/references/web-integration.md` — Web UI and REST API integration

When creating the companion PR, reference the SDK change PR so reviewers can see both
sides of the update.
