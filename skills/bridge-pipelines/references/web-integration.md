# Web Interface Integration

Bridge pipelines connect to the Poolside web interface through a dedicated Bridge UI and REST API. This document covers the end-to-end flow from code to execution.

## Architecture Overview

```
Git Repository (pipeline code)
        ↓
Bridge UI: Register Repository
        ↓
Index Commit → SDK Analysis (discovers pipelines/steps)
        ↓
Create Build → DAG Execution (Temporal workflows)
        ↓
Steps execute in sandboxes (agents, scripts, etc.)
```

**Backend:** Temporal-based workflow orchestration with PostgreSQL storage.
**Frontend:** React app at `/bridge` path.

## Web UI Pages

| Path | Purpose |
|------|---------|
| `/bridge/credentials` | Manage encrypted credentials (API keys, tokens) |
| `/bridge/repositories` | Register and manage git repositories |
| `/bridge/pipelines` | View discovered pipelines and their steps |
| `/bridge/step-runs` | Monitor pipeline step execution |
| `/bridge/agent-runs` | Track agent sessions linked to step runs |

## Workflow

### 1. Create Credentials (if needed)

Register encrypted credentials that steps can use via `credential_bindings`. Credentials are stored encrypted at rest and injected as environment variables during step execution.

### 2. Register a Repository

Point Bridge to your git repository containing pipeline code. Repositories are linked to credentials for git authentication.

### 3. Index a Commit

Indexing triggers SDK analysis:
1. Repository is cloned into a sandbox
2. `bridge config get-dsl` runs to discover pipelines and steps
3. Results (step definitions, dependencies, schemas) are stored in the database
4. Commit state transitions: `new` → `indexing` → `finished` (or `failed`)

After indexing, all pipelines and steps from that commit are visible in the UI.

### 4. Create and Execute a Build

A build groups pipeline steps for execution:
1. Select steps to run (must belong to the same repository)
2. System resolves the dependency DAG
3. Steps execute in parallel when their dependencies are satisfied
4. Each step runs in its own sandbox environment
5. Step results are passed to downstream dependents
6. Step states: `new` → `starting` → `running` → `finished` (or `failed`)

A temporary API credential is generated per build (valid 24 hours) and revoked on completion.

## REST API

Base path: `/v0/bridge/`

### Credentials

```
POST   /v0/bridge/credentials                          Create credential
GET    /v0/bridge/credentials                          List credentials
GET    /v0/bridge/credentials/{credential_id}          Get credential
PATCH  /v0/bridge/credentials/{credential_id}          Update credential
DELETE /v0/bridge/credentials/{credential_id}          Delete credential
```

### Repositories

```
POST   /v0/bridge/repositories                         Create repository
GET    /v0/bridge/repositories                         List repositories
GET    /v0/bridge/repositories/{repository_id}         Get repository
PATCH  /v0/bridge/repositories/{repository_id}         Update repository
DELETE /v0/bridge/repositories/{repository_id}         Delete repository
```

### Commits & Indexing

```
GET    /v0/bridge/repositories/{repo_id}/commits                  List commits
POST   /v0/bridge/repositories/{repo_id}/commits                  Index commit
GET    /v0/bridge/repositories/{repo_id}/commits/{commit_id}      Get commit
DELETE /v0/bridge/repositories/{repo_id}/commits/{commit_id}      Delete commit
```

### Pipelines & Steps

```
GET    /v0/bridge/repositories/{repo_id}/pipelines                          List pipelines
GET    /v0/bridge/repositories/{repo_id}/pipelines/{pipeline_rid}/versions  List versions
GET    /v0/bridge/repositories/{repo_id}/pipeline-steps                     List steps
GET    /v0/bridge/repositories/{repo_id}/pipeline-steps/{step_id}           Get step
GET    /v0/bridge/repositories/{repo_id}/pipeline-steps/{step_id}/file      Get step source
```

### Builds & Step Runs

```
POST   /v0/bridge/repositories/{repo_id}/build                              Create build
GET    /v0/bridge/repositories/{repo_id}/builds                             List builds
GET    /v0/bridge/repositories/{repo_id}/pipeline-step-runs                 List runs
GET    /v0/bridge/repositories/{repo_id}/pipeline-step-runs/filter          Filter runs
GET    /v0/bridge/repositories/{repo_id}/pipeline-step-runs/{run_id}        Get run
POST   /v0/bridge/repositories/{repo_id}/pipeline-step-runs/{run_id}/agent-sessions  Link agent session
```

## Stable Resource IDs (RIDs)

Pipelines and steps support optional `rid` (resource ID) fields — deterministic UUIDs that remain stable across renames. This allows renaming a pipeline or step in code without losing its identity in the database.

- Pipeline RID namespace: `b2c3d4e5-f6a7-5b8c-9d0e-1f2a3b4c5d6e`
- Step RID namespace: `a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d`

If not provided, Bridge generates RIDs automatically using UUID v3 (MD5) from these namespaces.

## Authorization

Bridge uses Cedar-based authorization with owner-scoped access control. All resources (credentials, repositories) are tenant-isolated. Key actions:

- `create-bridge-credential`, `list-bridge-credentials`, `get-bridge-credential`, etc.
- `create-bridge-repository`, `list-bridge-repositories`, `get-bridge-repository`, etc.
- `index-bridge-repository-commit`, `create-bridge-build`, `list-bridge-builds`, etc.
