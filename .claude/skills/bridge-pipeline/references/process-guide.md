# Bridge Pipeline Process Guide

This guide encodes the methodology for designing Bridge pipelines - the discovery, context gathering, and design thinking that determines *what* to build before *how* to build it.

---

## Section 1: Discovery - Understanding the Workflow

Before writing any code, understand the workflow you're automating.

### Questions to Ask

**What Is This Workflow?**
- What triggers this workflow? (event, schedule, manual request)
- What is the desired outcome? (decision, document, action, notification)
- Which category fits best? (see Section 2)

**What Do Humans Do Today?**
- Walk me through the steps someone takes to do this
- Where do they spend the most time? (usually data gathering: 60-80%)
- What data/systems do they access?
- Where do they need to think vs. follow rules?

**Context Requirements**
- What data sources are needed?
- What systems need integration? (APIs, databases, MCP tools)
- What credentials are required?
- Is there domain expertise encoded in the process?

**Step Design**
- Which activities are pure data gathering? → Programmatic
- Which activities require synthesis/judgment? → Agent
- Where should verification gates go?
- Do agent steps need shared context? → Session continuity

---

## Section 2: The 7 Workflow Categories

Identify which category your workflow belongs to. This guides context needs and step ratios.

| Category | What It Does | Context Needs | Examples |
|----------|-------------|---------------|----------|
| **Investigation** | Synthesize multiple data sources to find root cause | Multi-system data, historical patterns, domain knowledge | KYC/AML, Security alerts, Quality defects, Bug triage |
| **Authorization** | Check requests against policies/criteria | Policy databases, eligibility rules, document verification | Prior auth, Returns processing, FNOL triage, Compliance review |
| **Analysis** | Produce judgments about risk/performance/value | Historical data, risk models, scoring criteria | Claims adjudication, Denial management, Credit underwriting |
| **Planning** | Decide actions based on context and priorities | Current state, resource availability, priority criteria | Incident response, Demand exceptions, Support escalation |
| **Generation** | Produce structured content | Templates, prior work, brand guidelines | Proposals, PRDs, Test suites, Catalog enrichment |
| **Exception** | Identify and resolve problems | Original process data, error patterns, correction policies | Order exceptions, Code review, Record summarization |
| **Matching** | Match requirements to resources/options | Requirement profiles, available options, constraints | Clinical trial matching, Resource allocation, RFQ response |

### Context Requirements by Workflow Type

| Workflow Type | Data Integration | Judgment Complexity | Volume/Speed |
|--------------|------------------|---------------------|--------------|
| Investigation | HIGH (10+ systems) | HIGH | LOW |
| Authorization | MEDIUM | LOW-MEDIUM | HIGH |
| Analysis | MEDIUM-HIGH | HIGH | MEDIUM |
| Planning | MEDIUM | MEDIUM | HIGH (time-sensitive) |
| Generation | LOW-MEDIUM | MEDIUM | VARIES |
| Exception | MEDIUM | LOW-MEDIUM | HIGH |
| Matching | MEDIUM | MEDIUM-HIGH | VARIES |

---

## Section 3: Human Activity → Step Type Mapping

**Key Insight:** Humans doing workflows perform 4 distinct activities. Map these to step types:

| Human Activity | Time Spent | Step Type | Ratio |
|---------------|-----------|-----------|-------|
| **Data Aggregation** | 60-80% | Programmatic | 100% |
| **Context Enrichment** | 10-20% | Programmatic + light agent | 80-20% |
| **Judgment & Analysis** | 10-20% | Agent + programmatic verification | 30-70% |
| **Documentation** | 5-10% | Agent + programmatic validation | 40-60% |

### Key Principles

1. **"Analysts spend 60-80% of time gathering information"**
   → Make that 100% programmatic. This is where pipelines add the most value.

2. **"Catch hallucinations before they propagate"**
   → Always add verification after agent steps. Never trust raw agent output.

3. **"Inconsistent decision-making across analysts"**
   → This is where agents add value. Consistent reasoning with documented rationale.

4. **"Context switching between systems is slow"**
   → Programmatic steps aggregate data fast. Present it to agents in structured prompts.

### Activity Descriptions

**Data Aggregation (60-80% of human time)**
- Fetching records from systems
- Looking up related data
- Consolidating information from multiple sources
- Almost always should be programmatic

**Context Enrichment (10-20%)**
- Pulling historical patterns
- Finding related cases
- Enriching with external data
- Mostly programmatic, occasional agent for complex correlation

**Judgment & Analysis (10-20%)**
- Synthesizing findings
- Assessing risk/impact
- Making recommendations
- Agent steps with verification gates after

**Documentation (5-10%)**
- Writing summaries
- Creating reports
- Formatting for downstream systems
- Agent for narrative, programmatic for validation

---

## Section 4: Step Design Methodology

### Breaking Down the Pipeline

1. **List what humans do today** - Every action, in order
2. **Categorize each action** - Which of the 4 activities?
3. **Map to step types** - Using the ratios above
4. **Add verification gates** - After every agent step
5. **Determine session continuity** - Do agent steps need shared context?

### Session Continuity Decisions

**Use ContinueFrom (shared session) when:**
- Agent needs context from previous reasoning
- Building on investigation/design/implementation chain
- Conversational flow matters

**Use independent sessions when:**
- Steps are logically independent
- Processing different cases in parallel
- Fresh perspective is valuable

### Verification Gate Placement

After every agent step, ask:

| Agent Output | Verification Type |
|-------------|-------------------|
| Extracted specific values | Verify they exist in source data |
| Made classification | Validate against known categories |
| Generated content | Check completeness, format, policies |
| Made recommendation | Verify against business rules |

---

## Section 5: Iteration Framework

Pipelines evolve through iteration. Common patterns:

### Pattern: Added Verification After Agent Step
**Trigger:** Agent hallucinated a value that didn't exist
**Fix:** Add programmatic step to validate agent output against source

### Pattern: Merged Consecutive Agent Steps
**Trigger:** Two agent steps that naturally flow together
**Fix:** Combine into single step with session continuity

### Pattern: Split Agent Step into Design + Implement
**Trigger:** Agent jumping straight to implementation without planning
**Fix:** Separate design (think) from implement (do) for engineering rigor

### Pattern: Converted Agent to Programmatic
**Trigger:** Agent step with no real judgment needed
**Fix:** Replace with deterministic programmatic step

### Testing Individual Steps

Before integration:
1. Test programmatic steps with real data
2. Test agent prompts independently
3. Validate parsing against real agent outputs
4. Check session continuation preserves context

---

## Section 6: Case Study - Linear-to-PR Pipeline

### Workflow Category: INVESTIGATION + GENERATION
- Primary: Investigation (find root cause in codebase)
- Secondary: Generation (create PR with fix)

### Discovery: What Humans Do Today

1. **Data Aggregation (10%):** Fetch issue from Linear, find the repo
2. **Context Enrichment (10%):** Identify relevant files in codebase
3. **Judgment (60%):** Investigate root cause, design solution, implement fix
4. **Documentation (20%):** Create PR with explanation, update Linear

### Step Breakdown (Human Activity → Step Type)

| Human Activity | Step | Type | Rationale |
|---------------|------|------|-----------|
| Data Aggregation | Fetch Issue | Programmatic | Deterministic API call |
| Data Aggregation | Select Repo | Programmatic | Mapping lookup |
| Judgment | Investigate | Agent | Requires codebase exploration |
| Judgment | Design Solution | Agent | Requires engineering judgment |
| Judgment + Generation | Implement + PR | Agent | Code generation + PR creation |
| Documentation | Update Linear | Programmatic | Deterministic API post |

**Ratio:** 50% programmatic, 50% agent (judgment-intensive workflow)

### Key Learnings from Iteration

1. **Added Design step** - Engineering rigor: think before implementing
2. **Merged Implement and PR** - Natural workflow continuation
3. **Converted Linear update to programmatic** - No reasoning needed
4. **Added explicit owner/repo in prompts** - Prevent hallucination of repository details

### Session Continuity Design

```
Step 03 (Investigate) → Fresh session
     ↓ session_id
Step 05 (Design) → ContinueFrom investigation
     ↓ session_id
Step 06 (Implement + PR) → ContinueFrom design
```

All three agent steps share context because:
- Design needs investigation findings
- Implementation needs design decisions
- Natural conversational flow

---

## Summary: The Process

1. **Discover** - Understand the workflow (category, triggers, outcomes)
2. **Map** - List what humans do today (4 activities)
3. **Design** - Translate activities to steps (aggregation→programmatic, judgment→agent)
4. **Verify** - Add gates after agent steps (catch hallucinations)
5. **Iterate** - Refine based on real usage (merge, split, convert)

This process works across ANY workflow - from Linear-to-PR to KYC investigation to test generation.
