# Bridge Pipeline Integrations Reference

> **Version Notice:** The code examples below are templates showing integration patterns. The Bridge SDK evolves over time and is shipped per-repository. Before implementing:
> 1. Read the actual `bridge_sdk/` source in your target repository for current API signatures
> 2. Study existing pipelines in the repo as working examples
> 3. Adapt these patterns to match your SDK version
>
> The architectural patterns (GraphQL queries, prompt structures, parsing strategies) should remain applicable across versions.

## Table of Contents
1. [Linear API Integration](#linear-api-integration)
2. [GitHub MCP Integration](#github-mcp-integration)
3. [Agent Prompt Templates](#agent-prompt-templates)
4. [Programmatic Step Patterns](#programmatic-step-patterns)

---

## Linear API Integration

### Fetching Issues (GraphQL)

```python
import os
import httpx

def fetch_linear_issue(issue_identifier: str) -> dict:
    api_key = os.environ.get("LINEAR_API_KEY")

    query = """
    query GetIssue($id: String!) {
        issue(id: $id) {
            id
            identifier
            title
            description
            url
            priority
            team { id name }
            project { id name }
            labels { nodes { name } }
        }
    }
    """

    with httpx.Client() as client:
        response = client.post(
            "https://api.linear.app/graphql",
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
            },
            json={"query": query, "variables": {"id": issue_identifier}},
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
```

### Creating Comments

```python
def create_linear_comment(api_key: str, issue_id: str, body: str) -> dict:
    mutation = """
    mutation CreateComment($issueId: String!, $body: String!) {
        commentCreate(input: { issueId: $issueId, body: $body }) {
            success
            comment { id body createdAt }
        }
    }
    """

    with httpx.Client() as client:
        response = client.post(
            "https://api.linear.app/graphql",
            headers={
                "Authorization": api_key,
                "Content-Type": "application/json",
            },
            json={
                "query": mutation,
                "variables": {"issueId": issue_id, "body": body},
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
```

### Updating Issue State

```python
def update_issue_state(api_key: str, issue_id: str, state_name: str) -> dict:
    # First get team's workflow states
    get_states_query = """
    query GetIssueTeam($id: String!) {
        issue(id: $id) {
            team {
                states { nodes { id name } }
            }
        }
    }
    """

    # Then update with state ID
    update_mutation = """
    mutation UpdateIssue($id: String!, $stateId: String!) {
        issueUpdate(id: $id, input: { stateId: $stateId }) {
            success
            issue { id state { name } }
        }
    }
    """
```

---

## GitHub MCP Integration

### Agent Prompt for GitHub Operations

Always be explicit about owner and repo:

```python
GITHUB_PROMPT = """
## Repository Context

**Owner:** {repo_owner}
**Repository:** {repo_name}
**Full Path:** {repo_owner}/{repo_name}

## CRITICAL: GitHub MCP Tool Usage

For ALL GitHub MCP tool calls, you MUST use:
- `owner: "{repo_owner}"`
- `repo: "{repo_name}"`

### Available Tools

**Reading:**
- `get_file_contents` - Read file content
- `search_code` - Search for code patterns
- `list_commits` - View commit history

**Writing:**
- `create_branch` - Create new branch from base
- `create_or_update_file` - Write/update files (auto-commits)
- `create_pull_request` - Open a PR

### Example Tool Calls

Create branch:
```
create_branch(
    owner="{repo_owner}",
    repo="{repo_name}",
    branch="fix/issue_123",
    from_branch="main"
)
```

Read file:
```
get_file_contents(
    owner="{repo_owner}",
    repo="{repo_name}",
    path="src/auth.py"
)
```

Create PR:
```
create_pull_request(
    owner="{repo_owner}",
    repo="{repo_name}",
    title="Fix: Issue description",
    body="## Summary\\n...",
    head="fix/issue_123",
    base="main"
)
```
"""
```

### RepoInfo Model

```python
class RepoInfo(BaseModel):
    """Repository information with explicit owner."""
    owner: str      # GitHub org/user (e.g., "poolsideai")
    name: str       # Repo name (e.g., "bridge-sdk")
    github_url: str
    default_branch: str = "main"
```

---

## Agent Prompt Templates

### Investigation Prompt

```python
INVESTIGATION_PROMPT = """You are investigating a codebase to find the root cause of an issue.

## Context

**Owner:** {repo_owner}
**Repository:** {repo_name}
**Full Path:** {repo_owner}/{repo_name}

## Issue to Investigate

**ID:** {issue_id}
**Title:** {issue_title}

**Description:**
{description}

## Investigation Strategy

1. **Start with targeted searches** - Use grep/search for:
   - Keywords from issue title/description
   - Error messages
   - Function/class names

2. **Get repository overview** - Scan top-level structure

3. **Read only relevant sections** - Don't read entire files line-by-line

4. **Document findings** - Specific file paths and line numbers

## Important Guidelines

- **Prefer grep/search over browsing**
- **Be surgical, not exhaustive**
- **Stop when you have enough**
- **Avoid reading large files in chunks**
"""
```

### Solution Design Prompt

```python
DESIGN_PROMPT = """You are designing a solution for a code issue.

## Context

**Repository:** {repo_owner}/{repo_name}
**Issue:** {issue_id} - {issue_title}

## Investigation Findings

{investigation_response}

## Your Task: Design the Solution

### Step 1: Summarize Root Cause
Restate in 2-3 sentences.

### Step 2: Brainstorm Solutions
Propose 2-3 approaches. For each:
- Short name (e.g., "Approach A: Add null check")
- 2-3 sentence description
- Files/functions affected

### Step 3: Evaluate Each Solution
Analyze: Complexity, Risk, Maintainability, Completeness

### Step 4: Select Best Solution
Apply: Minimal change, Consistency, Low risk, Clarity

### Step 5: Create Implementation Plan
- Branch name
- Files to modify (with specific changes)
- Order of operations

## Output Format

```
## Root Cause Summary
[summary]

## Proposed Solutions
### Approach A: [Name]
...

## Selected Solution: [Name]
[justification]

## Implementation Plan
1. Create branch: fix/{issue_id_lower}
2. [steps...]
```

## Important: Do NOT write code - only design and plan
"""
```

### Implementation Prompt

```python
IMPLEMENTATION_PROMPT = """You are implementing a fix based on an approved design.

## Context

**Owner:** {repo_owner}
**Repository:** {repo_name}
**Issue:** {issue_id} - {issue_title}

## Solution Design

{design_response}

## Your Task: Implement and Create PR

### Part 1: Implementation

1. Create branch `fix/{issue_id_lower}`
2. Implement changes per the design
3. Write quality code matching existing style

### Part 2: Create Pull Request

Create PR with:
- Title: "Fix {issue_id}: [description]"
- Body: Summary, root cause, changes, testing

## GitHub MCP Tools

**CRITICAL:** Always use `owner: "{repo_owner}"` and `repo: "{repo_name}"`

## Required Output

```
## Implementation and PR Summary

**Status:** SUCCESS | FAILED
**Owner:** {repo_owner}
**Repository:** {repo_name}
**Branch:** fix/{issue_id_lower}

### Files Modified
- path/to/file.py: [description]

### Pull Request
**PR Number:** #[number]
**PR URL:** [url]
```
"""
```

---

## Programmatic Step Patterns

### API Data Fetching

```python
@step(
    name=PipelineSteps.FETCH_DATA.value,
    metadata={"type": "programmatic"},
    credential_bindings={"uuid": "API_KEY"},
)
def fetch_data(input_param: str) -> FetchResult:
    api_key = os.environ.get("API_KEY")
    if not api_key:
        raise ValueError("API_KEY environment variable is required")

    # Make API call
    with httpx.Client() as client:
        response = client.get(
            f"https://api.example.com/data/{input_param}",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()

    return FetchResult(data=data)
```

### Mapping/Lookup Step

```python
@step(
    name=PipelineSteps.SELECT_TARGET.value,
    metadata={"type": "programmatic"},
)
def select_target(
    input_result: Annotated[InputResult, step_result(PipelineSteps.INPUT.value)],
) -> SelectionResult:
    mapping = load_mapping_file()  # JSON config

    # Priority-based matching
    if input_result.project in mapping.get("projects", {}):
        return SelectionResult(
            target=mapping["projects"][input_result.project],
            matched_by="project",
        )

    if input_result.team in mapping.get("teams", {}):
        return SelectionResult(
            target=mapping["teams"][input_result.team],
            matched_by="team",
        )

    # Fallback
    return SelectionResult(
        target=mapping["default"],
        matched_by="default",
    )
```

### Result Formatting Step

```python
@step(
    name=PipelineSteps.FORMAT_OUTPUT.value,
    metadata={"type": "programmatic"},
)
def format_output(
    agent_result: Annotated[AgentResult, step_result(PipelineSteps.AGENT.value)],
) -> FormattedResult:
    # Extract key info from agent response
    pr_url = extract_pr_url(agent_result.response)
    files_changed = extract_files(agent_result.response)
    status = "SUCCESS" if pr_url else "FAILED"

    # Format for external system
    formatted = f"""
## Status: {status}
**PR:** {pr_url or 'N/A'}

### Files Changed
{chr(10).join(f'- {f}' for f in files_changed)}
"""

    return FormattedResult(
        status=status,
        pr_url=pr_url,
        formatted_output=formatted,
    )
```
