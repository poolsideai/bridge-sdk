# Agent Integration

## BridgeSidecarClient

The Bridge SDK provides a gRPC client for launching agents within pipeline steps.

```python
from bridge_sdk.bridge_sidecar_client import BridgeSidecarClient
from bridge_sdk.proto.bridge_sidecar_pb2 import ContinueFrom, RunDetail
```

### Starting an Agent

```python
with BridgeSidecarClient(host="localhost", port=50052) as client:
    agent_name, session_id, exit_result = client.start_agent(
        prompt="Your task here",
        agent_name="Malibu",           # optional, uses default if None
        directory="/path/to/workdir",   # optional working directory
    )
```

**Parameters:**
- `prompt` (str): The task for the agent
- `agent_name` (str, optional): Agent model to use (default: `"agent_1003_cc_v2_rc-fp8-tpr"`)
- `directory` (str, optional): Working directory for the agent
- `continue_from` (ContinueFrom, optional): Continue a previous session

**Returns:** `(agent_name, session_id, exit_result)`

### Getting Agent Output

`exit_result` is **not** the agent's work output — it's just a status/success message. To capture agent output, instruct the agent to write results to a file:

```python
import json

OUTPUT_FILE = "/tmp/agent_output.json"

@pipeline.step(metadata={"type": "agent"})
def run_analysis() -> dict:
    prompt = f"""Analyze the codebase and write a JSON report to {OUTPUT_FILE}.
    The JSON should have keys: summary, issues, recommendations."""

    with BridgeSidecarClient() as client:
        _, session_id, _ = client.start_agent(prompt=prompt)

    with open(OUTPUT_FILE) as f:
        return json.load(f)
```

### Continuing Agent Sessions

To continue from a previous agent session (preserving context):

```python
@pipeline.step(metadata={"type": "agent"})
def followup_step(
    prev: Annotated[HelloWorldResult, step_result(initial_step)],
) -> str:
    with BridgeSidecarClient() as client:
        _, session_id, _ = client.start_agent(
            prompt="Continue with the next task",
            agent_name="Malibu",
            continue_from=ContinueFrom(
                previous_run_detail=RunDetail(
                    agent_name="Malibu",
                    session_id=prev.session_id,
                ),
                continuation=ContinueFrom.NoCompactionStrategy(),
            ),
        )
        return session_id
```

**Continuation strategies:**
- `ContinueFrom.NoCompactionStrategy()` — preserve full context
- `ContinueFrom.CompactionStrategy()` — compact context before continuing

### Full Agent Pipeline Example

```python
from typing import Annotated, Optional
from pydantic import BaseModel
from bridge_sdk import Pipeline, step_result
from bridge_sdk.bridge_sidecar_client import BridgeSidecarClient
from bridge_sdk.proto.bridge_sidecar_pb2 import ContinueFrom, RunDetail

pipeline = Pipeline(
    name="agent_example",
    description="Pipeline demonstrating agent steps with dependencies",
)

class AgentResult(BaseModel):
    session_id: str
    output: str

@pipeline.step(metadata={"type": "agent"})
def hello_world_agent() -> AgentResult:
    """Start an agent session."""
    with BridgeSidecarClient() as client:
        _, session_id, res = client.start_agent(
            "say hello",
            agent_name="Malibu",
        )
        return AgentResult(session_id=session_id, output=res)

class ContinuationInput(BaseModel):
    additional_context: str

@pipeline.step(metadata={"type": "agent"})
def continuation_agent(
    input: ContinuationInput,
    prev_result: Annotated[AgentResult, step_result(hello_world_agent)],
) -> Optional[str]:
    """Continue from the previous agent session."""
    with BridgeSidecarClient() as client:
        _, session_id, _ = client.start_agent(
            "tell me what was done previously",
            agent_name="Malibu",
            continue_from=ContinueFrom(
                previous_run_detail=RunDetail(
                    agent_name="Malibu",
                    session_id=prev_result.session_id,
                ),
                continuation=ContinueFrom.NoCompactionStrategy(),
            ),
        )
        return session_id
```

## gRPC Proto Definition

The sidecar service is defined in `bridge_sdk/proto/bridge_sidecar.proto`:

```protobuf
service BridgeSidecarService {
  rpc StartAgent (StartAgentRequest) returns (StartAgentResponse);
}

message StartAgentRequest {
  string prompt = 1;
  string agent_name = 2;
  string directory = 3;
  ContinueFrom continue_from = 4;
}

message StartAgentResponse {
  RunDetail run_detail = 1;
  string exit_result = 3;
}

message RunDetail {
  string agent_name = 1;
  string session_id = 2;
}

message ContinueFrom {
  RunDetail previous_run_detail = 1;
  oneof compaction_strategy {
    NoCompactionStrategy continuation = 2;
    CompactionStrategy compaction = 3;
  }
}
```
