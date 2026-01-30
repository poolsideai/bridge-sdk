---
name: bridge-pipeline
description: |
  Create and modify Bridge SDK pipelines for Poolside's agent orchestration platform.
  Use this skill when: (1) Creating a new Bridge pipeline from scratch, (2) Adding steps to an existing pipeline,
  (3) Debugging Bridge pipeline issues, (4) Converting workflows to Bridge format,
  (5) Working with agent steps, programmatic steps, or MCP integrations in Bridge.
  Triggers: "create a bridge pipeline", "add a step", "bridge sdk", "agent step", "programmatic step",
  "credential bindings", "step_result", "BridgeSidecarClient".
---

# Bridge Pipeline Development

Build production-grade agentic workflows combining static programmatic steps with dynamic agent steps.

**Process-First Approach:** Before writing code, understand the workflow. This skill guides you through:
1. **Discovery** - Understanding what the workflow does and who does it today
2. **Categorization** - Identifying the workflow type (7 categories)
3. **Activity Mapping** - Translating human activities to step types
4. **Design** - Breaking down into programmatic and agent steps
5. **Implementation** - Building with SDK patterns

---

## 1. Discovery Phase

Before building a pipeline, answer these questions:

### What Is This Workflow?
- **Trigger:** What starts this workflow? (event, schedule, manual request)
- **Outcome:** What is the desired result? (decision, document, action, notification)
- **Category:** Which type fits best? (see Section 2)

### What Do Humans Do Today?
- Walk me through the steps someone takes to do this
- Where do they spend the most time? (usually data gathering: 60-80%)
- What data/systems do they access?
- Where do they need to think vs. follow rules?

### Context Requirements
- What data sources are needed?
- What systems need integration? (APIs, databases, MCP tools)
- What credentials are required?
- Is there domain expertise encoded in the process?

### Step Design Considerations
- Which activities are pure data gathering? → Programmatic
- Which activities require synthesis/judgment? → Agent
- Where should verification gates go?
- Do agent steps need shared context? → Session continuity

---

## 2. Workflow Categories

Identify your workflow's category to guide design decisions:

| Category | What It Does | Examples |
|----------|-------------|----------|
| **Investigation** | Synthesize multiple data sources to find root cause | KYC/AML, Security alerts, Bug triage |
| **Authorization** | Check requests against policies/criteria | Prior auth, Returns, Compliance review |
| **Analysis** | Produce judgments about risk/performance/value | Claims adjudication, Credit underwriting |
| **Planning** | Decide actions based on priorities/resources | Incident response, Support escalation |
| **Generation** | Produce structured content | Proposals, PRDs, Test suites |
| **Exception** | Identify and resolve problems in processes | Order exceptions, Code review |
| **Matching** | Match requirements to resources/options | Clinical trial matching, RFQ response |

**See:** `references/decision-trees.md` for category identification flowchart

---

## 3. Human Activity → Step Type Mapping

Humans doing workflows perform 4 distinct activities. Map these to step types:

| Human Activity | Time Spent | Step Type | Ratio |
|---------------|-----------|-----------|-------|
| **Data Aggregation** | 60-80% | Programmatic | 100% |
| **Context Enrichment** | 10-20% | Programmatic + light agent | 80-20% |
| **Judgment & Analysis** | 10-20% | Agent + programmatic verification | 30-70% |
| **Documentation** | 5-10% | Agent + programmatic validation | 40-60% |

**Key Principles:**
1. "Analysts spend 60-80% of time gathering information" → Make that 100% programmatic
2. "Catch hallucinations before they propagate" → Always verify after agent steps
3. "Inconsistent decision-making across analysts" → This is where agents add value

**See:** `references/process-guide.md` for detailed activity descriptions

---

## 4. Design Methodology

### Step Breakdown Process
1. **List** what humans do today - every action, in order
2. **Categorize** each action - which of the 4 activities?
3. **Map** to step types - using the ratios above
4. **Add** verification gates - after every agent step
5. **Determine** session continuity - do agent steps need shared context?

### Agent vs Programmatic Decision

```
Does this step require reasoning about ambiguous input?
├─ NO → Programmatic
│   Examples: Fetch data, lookup mapping, consolidate, post results
└─ YES → Does it involve synthesizing multiple sources?
    ├─ YES → Agent step (with verification after)
    │   Examples: Investigation, analysis, generation
    └─ NO → Could be either (prefer programmatic if deterministic)
```

### Session Continuity Decision

```
Do consecutive agent steps need shared context?
├─ YES → Use ContinueFrom with session_id
│   Examples: Investigation → Design → Implementation
└─ NO → Independent sessions
    Example: Parallel processing of different cases
```

### Verification Placement

After agent step, add verification for:
- **Extracted values** → Verify they exist in source data
- **Classifications** → Validate against known categories
- **Generated content** → Check completeness, format, policies
- **Recommendations** → Verify against business rules

**See:** `references/decision-trees.md` for complete decision flowcharts

---

## 5. Implementation Patterns

### Important: SDK Version Awareness

The Bridge SDK is shipped per-repository and evolves over time. **Before writing any pipeline code:**

1. **Read the SDK source** in the target repository (typically `bridge_sdk/` or similar)
2. **Study existing pipelines** in the repo as templates for current patterns
3. **Check `pyproject.toml`** for `[tool.bridge]` configuration requirements

The patterns below describe **architectural principles** that remain stable. For exact API signatures, always defer to the SDK source in your target repository.

### Two Step Types

| Type | Purpose | Characteristics |
|------|---------|-----------------|
| **Programmatic** | Deterministic operations | API calls, data transformation, validation, parsing |
| **Agent** | LLM-powered reasoning | Investigation, design, implementation, creative tasks |

### Key Principle: Alternate Agent and Programmatic Steps

```
[Programmatic] → [Agent] → [Programmatic] → [Agent] → [Programmatic]
   Fetch data     Reason     Validate        Act        Report
```

**Why this matters:**
- Agents reason and make decisions
- Programmatic steps validate, transform, and integrate
- Creates audit trails and verification gates
- Prevents agent hallucinations from propagating

---

## 6. Architectural Patterns

### Pattern 1: Step Dependencies via Annotations

Dependencies between steps are declared through type annotations. The framework infers execution order automatically.

**Principle:** Each step function's parameters declare what previous step outputs it needs. The `step_result()` annotation marks which step provides that data.

**To implement:** Read your SDK's `annotations.py` or `step.py` for exact `step_result()` usage.

### Pattern 2: Credential Injection

Credentials are never hardcoded. They're bound by UUID in the step decorator and injected as environment variables at runtime.

**Principle:**
1. Obtain credential UUIDs from Bridge UI
2. Map UUID → environment variable name in step decorator
3. Access via `os.environ.get("VAR_NAME")` in step code
4. Always validate credentials exist before using

### Pattern 3: Session Continuation for Agents

Agent steps can continue from previous agent sessions, preserving full conversation context.

**Principle:**
- First agent step: Fresh session
- Subsequent agent steps: Continue from previous session ID
- Store `session_id` in step results for chaining
- Use `NoCompactionStrategy` to preserve full history

**To implement:** Read your SDK's `bridge_sidecar_client.py` and proto definitions for continuation API.

### Pattern 4: Structured Agent Prompts

Agent prompts should be explicit and structured to ensure reliable outputs.

**Template structure:**
```
## Context
[Inject all relevant data from previous steps]

## Task
[Clear, specific instructions]

## Constraints
[Explicit parameters, tool usage rules, boundaries]

## Required Output Format
[Exact format for parsing by subsequent programmatic steps]
```

### Pattern 5: Programmatic Steps for Parsing

Never trust raw agent output. Add programmatic steps to:
- Extract structured data (URLs, IDs, status)
- Validate output format
- Handle missing/malformed sections gracefully
- Use multiple parsing strategies with fallbacks

---

## 7. Project Structure

```
pipeline_name/
├── __init__.py           # Export all steps for discovery
├── models.py             # Pydantic models + step enum
├── step_01_*.py          # Steps numbered for clarity
├── step_02_*.py
├── ...
└── config files          # repo_mapping.json, etc.
```

**Naming convention:** `step_NN_description.py` (e.g., `step_01_fetch_issue.py`)

---

## 8. Workflow: Creating a New Pipeline

1. **Discovery Phase**
   - Answer the questions in Section 1
   - Identify workflow category (Section 2)
   - Map human activities to step types (Section 3)

2. **Explore the SDK**
   - Read `bridge_sdk/__init__.py` for public API
   - Read `bridge_sdk/step.py` for `@step` decorator parameters
   - Read `bridge_sdk/annotations.py` for `step_result()` usage
   - Read `bridge_sdk/bridge_sidecar_client.py` for agent invocation

3. **Study existing pipelines** in the repository as templates

4. **Design step sequence**
   - Map out programmatic vs agent steps
   - Identify data flow between steps
   - Plan session continuation for agent chains
   - Place verification gates after agent steps

5. **Create models.py**
   - Define step enum with all step names
   - Define Pydantic models for each step's output
   - Include `session_id: str` field for agent step results

6. **Implement steps** following patterns from existing pipelines

7. **Validate with `bridge check`** (or equivalent CLI command)

---

## 9. Anti-Patterns to Avoid

1. **Skipping discovery** - Understand the workflow before building
2. **Hardcoding API signatures** - Always read the SDK in your repo
3. **Letting agents guess parameters** - Be explicit about owner, repo, credentials in prompts
4. **Trusting raw agent output** - Parse and validate in programmatic steps
5. **Skipping verification gates** - Add programmatic validation after every agent step
6. **Using generic agent names** - Use specific names configured in Bridge
7. **Blocking on non-critical failures** - Use try/except for optional operations (e.g., status updates)

---

## 10. Debugging

- **Check dependencies:** Use Bridge CLI to visualize step graph
- **Verify credentials:** Ensure UUIDs match Bridge UI configuration
- **Test prompts independently:** Run agent prompts outside pipeline first
- **Review trajectory logs:** Check full prompts, tool calls, and outputs in Bridge UI
- **Validate parsing:** Test extraction functions against real agent outputs

---

## References

- `references/process-guide.md` - Full methodology, workflow categories, human activities, case studies
- `references/decision-trees.md` - Visual decision frameworks for design choices
- `references/integrations.md` - Integration patterns (Linear, GitHub MCP, etc.)
- `references/troubleshooting.md` - Common errors and solutions

**Always prioritize reading the actual SDK and existing pipelines in your target repository over these reference docs.**
