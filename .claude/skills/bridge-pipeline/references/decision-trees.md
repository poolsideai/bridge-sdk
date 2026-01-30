# Bridge Pipeline Decision Trees

Visual decision frameworks for designing Bridge pipelines.

---

## 1. Workflow Category Identification

**Question: What is the primary purpose of this workflow?**

```
What is the primary purpose of this workflow?

├─ Finding root cause from multiple data sources?
│   └─ INVESTIGATION
│       Examples: KYC/AML, Security alerts, Quality defects, Bug triage
│       Characteristics: High data integration, high judgment, low volume
│
├─ Checking requests against policies/criteria?
│   └─ AUTHORIZATION
│       Examples: Prior auth, Returns processing, FNOL triage, Compliance review
│       Characteristics: Medium data, low-medium judgment, high volume
│
├─ Producing judgments about risk/performance/value?
│   └─ ANALYSIS
│       Examples: Claims adjudication, Denial appeals, Credit underwriting
│       Characteristics: Medium-high data, high judgment, medium volume
│
├─ Deciding actions based on priorities/resources?
│   └─ PLANNING
│       Examples: Incident response, Demand exceptions, Support escalation
│       Characteristics: Medium data, medium judgment, high volume (time-sensitive)
│
├─ Producing structured content/documents?
│   └─ GENERATION
│       Examples: Proposals, Test suites, PRDs, Catalog enrichment
│       Characteristics: Low-medium data, medium judgment, varies
│
├─ Identifying and resolving problems in processes?
│   └─ EXCEPTION
│       Examples: Order exceptions, Record summarization, Code review
│       Characteristics: Medium data, low-medium judgment, high volume
│
└─ Matching requirements to available options?
    └─ MATCHING
        Examples: Clinical trial matching, Resource allocation, RFQ response
        Characteristics: Medium data, medium-high judgment, varies
```

---

## 2. Human Activity → Step Type Mapping

**Question: What is this step doing?**

```
What is this step doing?

├─ Gathering data from systems?
│   └─ PROGRAMMATIC
│       - API calls to fetch records
│       - Database queries
│       - File parsing
│       - Data transformation
│       Ratio: 100% programmatic
│
├─ Pulling related records/context?
│   └─ MOSTLY PROGRAMMATIC
│       - Standard lookups → Programmatic
│       - Complex correlation → Light agent
│       Ratio: 80% programmatic, 20% agent
│
├─ Synthesizing, assessing, making recommendations?
│   └─ AGENT + VERIFICATION
│       - Investigation findings
│       - Risk assessment
│       - Design decisions
│       - Recommendations
│       Ratio: 30% agent, 70% programmatic (verification)
│
└─ Writing narratives, reports, documents?
    └─ AGENT + VALIDATION
        - Summary generation
        - Report writing
        - Documentation
        Ratio: 40% agent, 60% programmatic (validation)
```

---

## 3. Agent vs Programmatic Decision Tree

**Question: Should this step be agent or programmatic?**

```
Does this step require reasoning about ambiguous input?

├─ NO → PROGRAMMATIC
│   │
│   └─ Examples:
│       - Fetch data from API
│       - Lookup mapping table
│       - Consolidate records
│       - Post results to system
│       - Parse structured output
│       - Validate against schema
│
└─ YES → Does it involve synthesizing multiple sources?
    │
    ├─ YES → AGENT STEP (with verification after)
    │   │
    │   └─ Examples:
    │       - Investigate root cause
    │       - Analyze risk factors
    │       - Design solution approach
    │       - Generate documentation
    │       - Make recommendations
    │
    └─ NO → Could be either (prefer programmatic if deterministic)
        │
        ├─ Deterministic rules exist → PROGRAMMATIC
        │   Examples: Classification by defined criteria
        │
        └─ Requires interpretation → AGENT
            Examples: Ambiguous text classification
```

---

## 4. Session Continuity Decision Tree

**Question: Do consecutive agent steps need shared context?**

```
Do consecutive agent steps need shared context?

├─ YES → Use ContinueFrom with session_id
│   │
│   ├─ Previous reasoning informs current step?
│   │   └─ Yes: Investigation → Design → Implementation
│   │
│   ├─ Building on previous analysis?
│   │   └─ Yes: Analysis → Recommendation → Documentation
│   │
│   └─ Conversational flow matters?
│       └─ Yes: Question → Follow-up → Resolution
│
└─ NO → Independent sessions
    │
    ├─ Processing different cases?
    │   └─ Parallel case processing
    │
    ├─ Fresh perspective valuable?
    │   └─ Review/validation steps
    │
    └─ Logically independent operations?
        └─ Separate workflows triggered by same event
```

---

## 5. Verification Placement Decision Tree

**Question: What verification is needed after this agent step?**

```
After agent step, what did the agent produce?

├─ Extracted specific values (IDs, URLs, names)?
│   └─ VERIFY: Values exist in source data
│       - Parse output for extracted values
│       - Check against original input data
│       - Fail if value doesn't exist in source
│
├─ Made a classification or categorization?
│   └─ VALIDATE: Against known categories
│       - Check output matches valid enum
│       - Verify confidence threshold met
│       - Fallback for unknown categories
│
├─ Generated content (text, code, documents)?
│   └─ CHECK: Completeness, format, policies
│       - Required sections present?
│       - Format matches template?
│       - Policy rules satisfied?
│
└─ Made a recommendation or decision?
    └─ VERIFY: Against business rules
        - Recommendation within valid options?
        - Prerequisites met?
        - Audit trail complete?

PRINCIPLE: "Catch hallucinations before they propagate"
```

---

## 6. Step Ratio Guidelines by Category

**Quick reference for expected step ratios:**

```
Investigation Workflows (KYC, Security alerts)
├─ Programmatic: 40-50%
├─ Agent: 40-50%
└─ Verification: 10-20%
    → Heavy on both data gathering and judgment

Authorization Workflows (Prior auth, Returns)
├─ Programmatic: 60-70%
├─ Agent: 20-30%
└─ Verification: 10%
    → Mostly rule-based with some judgment

Analysis Workflows (Claims, Underwriting)
├─ Programmatic: 50-60%
├─ Agent: 30-40%
└─ Verification: 10%
    → Balanced data and judgment

Planning Workflows (Incident response)
├─ Programmatic: 50-60%
├─ Agent: 30-40%
└─ Verification: 10%
    → Fast turnaround, moderate judgment

Generation Workflows (Proposals, PRDs)
├─ Programmatic: 30-40%
├─ Agent: 50-60%
└─ Verification: 10%
    → Heavy on content creation

Exception Workflows (Order exceptions)
├─ Programmatic: 60-70%
├─ Agent: 20-30%
└─ Verification: 10%
    → Mostly pattern matching

Matching Workflows (Clinical trials)
├─ Programmatic: 50-60%
├─ Agent: 30-40%
└─ Verification: 10%
    → Balanced criteria matching
```

---

## 7. Iteration Pattern Decision Tree

**Question: What change is needed based on observed behavior?**

```
What problem are you observing?

├─ Agent hallucinated values that don't exist?
│   └─ ADD: Verification step after agent
│       - Parse agent output
│       - Validate against source data
│       - Fail fast if invalid
│
├─ Two agent steps feel awkward separately?
│   └─ MERGE: Into single step with session continuity
│       - Combine prompts
│       - Use ContinueFrom if already chained
│       - Maintain conversation flow
│
├─ Agent jumping to implementation without thinking?
│   └─ SPLIT: Into design + implement steps
│       - Step 1: Design approach (output: plan)
│       - Step 2: Execute plan (input: plan from step 1)
│       - Use session continuity between them
│
├─ Agent step has no real judgment needed?
│   └─ CONVERT: To programmatic step
│       - Identify the deterministic logic
│       - Implement as code
│       - Remove agent overhead
│
└─ Pipeline too slow?
    └─ PARALLELIZE: Independent operations
        - Identify steps with no dependencies
        - Run data fetches in parallel
        - Merge before dependent steps
```

---

## Summary: Decision Flow

```
1. CATEGORIZE the workflow
   └─ Use Tree #1 to identify Investigation/Authorization/etc.

2. MAP human activities to step types
   └─ Use Tree #2 for each activity in the workflow

3. DECIDE agent vs programmatic for each step
   └─ Use Tree #3 for ambiguous cases

4. DETERMINE session continuity
   └─ Use Tree #4 for consecutive agent steps

5. PLACE verification gates
   └─ Use Tree #5 after every agent step

6. CHECK ratios against guidelines
   └─ Use Tree #6 for sanity check

7. ITERATE based on observed behavior
   └─ Use Tree #7 when refining the pipeline
```
