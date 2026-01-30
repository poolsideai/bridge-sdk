# Bridge Pipeline Troubleshooting Guide

> **Version Notice:** The code examples below reflect patterns at the time of writing. The Bridge SDK evolves over time and is shipped per-repository. Always verify exact API signatures against the `bridge_sdk/` source in your target repository. The error messages and solutions described here should remain applicable across versions.

## Table of Contents
1. [Common Errors](#common-errors)
2. [Dependency Issues](#dependency-issues)
3. [Credential Problems](#credential-problems)
4. [Agent Step Failures](#agent-step-failures)
5. [MCP Tool Issues](#mcp-tool-issues)

---

## Common Errors

### "Missing cached results for: StepName"

**Cause:** The pipeline structure changed (e.g., step renamed or merged) but the workflow was started with old structure.

**Solution:** Re-index the pipeline in Bridge and start a new workflow run. Old cached results are incompatible with new step names.

### "depends_on parameter not recognized"

**Cause:** Using `depends_on=` in the `@step` decorator.

**Solution:** Remove `depends_on`. Dependencies are automatically inferred from `step_result()` annotations:

```python
# WRONG
@step(name="Step2", depends_on=["Step1"])
def step_2(...):

# CORRECT - dependency inferred from annotation
@step(name="Step2")
def step_2(
    prev: Annotated[Step1Result, step_result("Step1")],
):
```

### "agent not found: AgentName"

**Cause:** Agent name in code doesn't match configured agent in Bridge.

**Solution:** Check the exact agent name in Bridge UI and use it:

```python
with BridgeSidecarClient() as client:
    _, session_id, response = client.start_agent(
        prompt,
        agent_name="exact_agent_name_from_bridge",  # Must match
    )
```

### "Response parsing error: Could not extract JSON"

**Cause:** Trying to parse agent response as JSON when it's not.

**Solution:** Agent steps should return raw `session_id` and `response`. Parse structured output programmatically:

```python
# CORRECT - simple return
return AgentResult(session_id=session_id, response=response)

# Parse in a subsequent programmatic step if needed
def format_result(agent_result):
    pr_url = extract_pr_url(agent_result.response)
    return FormattedResult(pr_url=pr_url)
```

---

## Dependency Issues

### Step runs before its dependency

**Cause:** `step_result()` not using the correct step name.

**Check:**
```python
class PipelineSteps(Enum):
    STEP_ONE = "StepOne"  # This is the value
    STEP_TWO = "StepTwo"

# Must use .value
@step(name=PipelineSteps.STEP_TWO.value)
def step_two(
    prev: Annotated[StepOneResult, step_result(PipelineSteps.STEP_ONE.value)],
    #                                          ^^^^^^^^^^^^^^^^^^^^^^^^^ Use .value
):
```

### Circular dependency detected

**Cause:** Step A depends on Step B which depends on Step A.

**Solution:** Restructure pipeline. Consider splitting one step into two or reordering.

---

## Credential Problems

### "Environment variable not set"

**Cause:** Credential binding UUID doesn't match Bridge configuration.

**Solution:**
1. Get correct UUID from Bridge UI (Credentials section)
2. Update step decorator:

```python
@step(
    name=PipelineSteps.STEP.value,
    credential_bindings={
        "correct-uuid-from-bridge": "ENV_VAR_NAME",
    },
)
```

### Credential works locally but not in Bridge

**Cause:** Local env var set but Bridge credential not configured.

**Solution:** Create credential in Bridge UI with same UUID referenced in code.

---

## Agent Step Failures

### Agent uses wrong repository/organization

**Cause:** Agent defaults to incorrect values, prompt not explicit enough.

**Solution:** Add explicit context with CRITICAL emphasis:

```python
PROMPT = """
**Owner:** {repo_owner}
**Repository:** {repo_name}
**Full Path:** {repo_owner}/{repo_name}

**CRITICAL: For ALL GitHub MCP tool calls, you MUST use:**
- `owner: "{repo_owner}"`
- `repo: "{repo_name}"`
"""
```

### Agent reads files inefficiently (line by line)

**Cause:** Prompt doesn't discourage this behavior.

**Solution:** Add explicit guidance:

```python
PROMPT = """
## Important Guidelines

- **Prefer grep/search over browsing** - Always search first
- **Be surgical, not exhaustive** - Don't read every file
- **Avoid reading large files in chunks** - Search within instead
"""
```

### Agent response is too verbose

**Cause:** No required output format specified.

**Solution:** Add structured output requirement:

```python
PROMPT = """
## Required Output

You MUST end your response with this exact format:

```
## Summary
**Status:** SUCCESS | FAILED
**Key Result:** [one line]
```
"""
```

---

## MCP Tool Issues

### GitHub MCP: "404 Not Found" for repository

**Cause:** Wrong owner or repo name in MCP call.

**Solution:**
1. Add explicit owner/repo to prompt
2. Include in RepoInfo model:

```python
class RepoInfo(BaseModel):
    owner: str  # "poolsideai" not "poolside"
    name: str
    github_url: str
```

### Linear MCP: OAuth required

**Cause:** Linear MCP uses OAuth, not API key.

**Solution:** Use Linear GraphQL API directly in programmatic steps instead of MCP:

```python
@step(
    name=PipelineSteps.UPDATE_LINEAR.value,
    metadata={"type": "programmatic"},  # Not agent
    credential_bindings={"uuid": "LINEAR_API_KEY"},
)
def update_linear(result: PrevResult) -> UpdateResult:
    api_key = os.environ.get("LINEAR_API_KEY")
    # Direct GraphQL call instead of MCP
```

### MCP tool call times out

**Cause:** Long-running operation or rate limiting.

**Solution:**
1. Break into smaller operations
2. Add retry logic in programmatic wrapper
3. Check API rate limits

---

## Debugging Tips

### Run `bridge check` locally

Validates pipeline structure before pushing:

```bash
cd /path/to/pipeline
bridge check
```

### Check step execution order

Review the dependency graph:

```python
# Print inferred dependencies
for step in pipeline.steps:
    print(f"{step.name} depends on: {step.depends_on}")
```

### Test agent prompts independently

Before adding to pipeline:

```bash
bazelisk run cmd/pool -- \
  --agent-name your_agent \
  --prompt-file /path/to/prompt.txt \
  --placeholder KEY=value
```

### Review trajectory logs

In Bridge UI, check:
- Full prompts sent to agent
- Every tool call with inputs/outputs
- Timing for each operation
- Complete error messages
