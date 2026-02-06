# Bridge CLI Reference

The Bridge CLI is the primary tool for local development and validation.

## Setup

Create a `main.py` entry point:

```python
from bridge_sdk.cli import main

if __name__ == "__main__":
    main()
```

Run via: `uv run bridge <command>` (or `python -m bridge_sdk.cli`)

## Commands

### `bridge check`

Validate project setup and discover steps.

```bash
uv run bridge check
```

Checks:
1. `pyproject.toml` exists
2. `[build-system]` section is present
3. `[tool.bridge]` section with `modules` is configured
4. All listed modules are importable
5. Discovered steps are listed

Exit codes: `0` = success, `1` = error or warnings.

**Common import errors:**
```
Make sure your step modules are importable. Options:
  1. Install your project: pip install -e . (or uv sync)
  2. Set PYTHONPATH: export PYTHONPATH="${PYTHONPATH}:$(pwd)"
  3. Use --modules with fully qualified package paths
```

### `bridge config get-dsl`

Generate JSON DSL of all discovered pipelines and steps.

```bash
uv run bridge config get-dsl
uv run bridge config get-dsl --modules my_project.steps --output-file /tmp/dsl.json
```

**Options:**
- `--modules`: Override module discovery (comma-separated)
- `--output-file`: Output path (default: `/tmp/config_get_dsl/dsl.json`)

**Output format:**
```json
{
  "steps": {
    "step_name": {
      "name": "step_name",
      "pipeline": "pipeline_name",
      "description": "...",
      "depends_on": ["upstream_step"],
      "params_json_schema": {},
      "return_json_schema": {},
      "params_from_step_results": {"param": "upstream_step"},
      "credential_bindings": {},
      "file_path": "my_project/steps.py",
      "file_line_number": 15
    }
  },
  "pipelines": {
    "pipeline_name": {
      "name": "pipeline_name",
      "rid": "uuid-optional",
      "description": "..."
    }
  }
}
```

### `bridge run`

Execute a single step locally for testing.

```bash
uv run bridge run \
  --step step_name \
  --input '{"param1": "value"}' \
  --results '{"upstream_step": {"result": "data"}}'
```

**Options:**
- `--step`: Step name (required)
- `--input`: Input JSON string (required)
- `--results`: Step results JSON string (provide this or `--results-file`)
- `--results-file`: Path to JSON file with cached upstream results
- `--output-file`: Write output to file
- `--modules`: Override module discovery

When both `--input` and `--results` provide values for the same parameter, input takes precedence.
