#!/usr/bin/env python3
"""CLI runner for executing Steps with their setup and post-execution scripts.

Version Compatibility:
This script imports STEP_REGISTRY from 'lib', which resolves based on PYTHONPATH.
The entrypoint.sh sets PYTHONPATH so the cloned repo's bridge-sdk version takes precedence.
This ensures both the cloned repo's code and this discovery script use the same bridge-sdk
version, preventing version mismatch issues. The STEP_REGISTRY is shared because Python
modules are singletons - all imports of 'lib.step' reference the same module instance.
"""

import argparse
import importlib
import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import json

from pydantic import BaseModel

# Import from 'lib' - resolves to cloned repo's bridge-sdk version if available,
# otherwise falls back to /app/lib (this discovery script's version)
from lib import STEP_REGISTRY, StepRecord, get_dsl_output

# Default output file path (defined once, used throughout)
DEFAULT_OUTPUT_FILE = "/tmp/step_result.json"


def discover_all_modules(base_path: str) -> List[str]:
    """Discover all Python modules in a directory tree."""
    modules = []
    base = Path(base_path).resolve()

    if not base.exists():
        return modules

    # Track which directories are packages (have __init__.py)
    package_dirs = set()

    # First pass: identify all package directories
    for root, dirs, files in os.walk(base):
        root_path = Path(root)
        if (root_path / "__init__.py").exists():
            package_dirs.add(root_path)

    # Second pass: find all importable modules
    for root, dirs, files in os.walk(base):
        # Skip hidden directories and common non-module directories
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".")
            and d not in ["__pycache__", "node_modules", ".git", "venv", ".venv"]
        ]

        root_path = Path(root)

        # Check if this directory or any parent is a package, or if it's the base directory
        is_importable = (
            root_path == base  # Base directory - always importable
            or root_path in package_dirs  # Has __init__.py
            or any(
                parent in package_dirs for parent in root_path.parents
            )  # Parent is a package
        )

        if is_importable:
            # Find all Python files in this directory
            for file in files:
                if file.endswith(".py") and not file.startswith("__"):
                    # Calculate relative module path
                    rel_path = root_path.relative_to(base)
                    if rel_path == Path("."):
                        module_name = file[:-3]  # Remove .py extension
                    else:
                        # Build module path from directory parts + filename
                        module_parts = list(rel_path.parts) + [file[:-3]]
                        module_name = ".".join(module_parts)

                    modules.append(module_name)

    return sorted(set(modules))  # Remove duplicates and sort


def discover_steps(
    module_path: Optional[str] = None, base_path: Optional[str] = None
) -> Dict[str, StepRecord]:
    """Dynamically discover all classes decorated with @step.

    This function imports modules from the cloned repository, which causes their
    @step decorators to execute and register steps in STEP_REGISTRY. The STEP_REGISTRY
    is imported from 'lib', which (due to PYTHONPATH ordering) resolves to the cloned
    repo's bridge-sdk version, ensuring version compatibility.

    If module_path is provided, imports that specific module.
    If base_path is provided, discovers and imports all modules from that path.
    If neither is provided, uses the current working directory.
    """
    if module_path:
        # Import a specific module
        try:
            importlib.import_module(module_path)
        except ImportError as e:
            print(f"Error importing module {module_path}: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Discover all modules from base_path
        if base_path is None:
            base_path = os.getcwd()

        modules = discover_all_modules(base_path)
        if not modules:
            print(f"No Python modules found in {base_path}", file=sys.stderr)
            sys.exit(1)

        # Import all discovered modules
        import_errors = []
        for module_name in modules:
            try:
                importlib.import_module(module_name)
            except ImportError as e:
                # Collect errors but don't fail immediately - some modules might not be importable
                import_errors.append(f"{module_name}: {e}")
            except Exception as e:
                # Other errors (syntax, etc.) should be reported
                print(f"Error importing module {module_name}: {e}", file=sys.stderr)

        if import_errors and not STEP_REGISTRY:
            # Only fail if we got errors AND no steps were discovered
            print("Errors importing some modules:", file=sys.stderr)
            for error in import_errors:
                print(f"  {error}", file=sys.stderr)
            sys.exit(1)

    return STEP_REGISTRY


def cmd_config_get_dsl(args):
    """Handle 'config get-dsl' command."""
    if args.module:
        # Discover steps from a specific module
        discover_steps(module_path=args.module)
    else:
        # Discover all steps from the base path
        base_path = args.base_path or os.environ.get("CLONE_DIR", os.getcwd())
        discover_steps(base_path=base_path)

    # Get DSL output from the registry
    dsl_output = get_dsl_output()
    json_output = json.dumps(dsl_output, indent=2)

    # Always print JSON to stdout for debugging purposes
    print(json_output)

    # Validate that output path is provided (should always have a value from parser default)
    if not args.output:
        print("Error: --output is required and cannot be empty", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(json_output)
    print(f"DSL output written to: {args.output}", file=sys.stderr)


def cmd_run_step(args):
    """Handle 'run' command to execute a step."""
    # 1. Discover steps from the module
    steps = discover_steps(args.module)
    step_name = args.step

    # 2. Find the step by name
    if step_name not in steps:
        print(steps)
        print(f"Error: Step '{args.step}' not found in module '{args.module}'")
        print(f"Available steps: {', '.join(steps.keys())}")
        sys.exit(1)

    # Parse results JSON
    try:
        cached_results = json.loads(args.results)
    except json.JSONDecodeError as e:
        print(f"Error parsing --results JSON: {e}")
        sys.exit(1)

    # 3. Get the step function and metadata
    step_func = steps[step_name].func
    step_metadata = steps[step_name].data

    # Verify dependencies are available
    dependencies = step_metadata.depends_on_steps or []
    missing_deps = [dep for dep in dependencies if dep not in cached_results]
    if missing_deps:
        raise ValueError(f"Missing cached results for: {', '.join(missing_deps)}")

    # 4. Build arguments based on parameter schema and step result mappings
    from typing import get_type_hints

    call_params = {}
    type_hints = get_type_hints(step_func)
    params_from_step_results = step_metadata.params_from_step_results or {}

    # Get parameter names from the JSON schema (excludes 'return')
    param_names = [
        name
        for name in step_metadata.params_json_schema.get("properties", {}).keys()
        if name != "return"
    ]

    # Parse the input JSON
    try:
        input_data = json.loads(args.input)
    except json.JSONDecodeError as e:
        print(f"Error parsing --input JSON: {e}")
        sys.exit(1)

    for param_name in param_names:
        # Check if it's a step result parameter
        if param_name in params_from_step_results:
            step_result_name = params_from_step_results[param_name]
            if step_result_name in cached_results:
                cached_value = cached_results[step_result_name]
                param_type = type_hints.get(param_name, Any)
                call_params[param_name] = resolve_step_input(cached_value, param_type)
            else:
                raise ValueError(
                    f"Step result '{step_result_name}' not found in cached results"
                )
        else:
            # It's a step input parameter - use the parsed input_data
            param_type = type_hints.get(param_name, Any)
            call_params[param_name] = resolve_step_input(input_data, param_type)

    # 5. Call the step function
    try:
        result = step_func(**call_params)
        print(f"Step '{args.step}' executed successfully")
        print(f"Result: {result}")

        # Write result to JSON file
        output_file = os.getenv("OUTPUT_FILE", "/tmp/step_result.json")
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert result to JSON-serializable format
        if isinstance(result, BaseModel):
            result_data = result.model_dump()
        elif isinstance(result, (dict, list, str, int, float, bool, type(None))):
            result_data = result
        else:
            # For other types, convert to string representation
            result_data = str(result)

        with open(output_path, "w") as f:
            json.dump(result_data, f, indent=2)

        print(f"Result written to: {output_file}")
    except Exception as e:
        print(f"Error executing step '{args.step}': {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def resolve_step_input(cached_value: Any, actual_type: Any) -> Any:
    """If the value is a pydantic model, we attempt to deserialize/validate, otherwise we pass the input as is"""
    if isinstance(actual_type, type) and issubclass(actual_type, BaseModel):
        # Deserialize to Pydantic model
        if isinstance(cached_value, dict):
            return actual_type(**cached_value)
        elif isinstance(cached_value, str):
            return actual_type.model_validate_json(cached_value)
        else:
            return cached_value
    else:
        # Pass as-is
        return cached_value


def main():
    parser = argparse.ArgumentParser(
        description="CLI for discovering and running Steps"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # 'config get-dsl' command
    config_parser = subparsers.add_parser("config", help="Configuration commands")
    config_subparsers = config_parser.add_subparsers(dest="config_command")

    get_dsl_parser = config_subparsers.add_parser(
        "get-dsl", help="Get DSL for discovered steps"
    )
    get_dsl_parser.add_argument(
        "--module",
        default=None,
        help="Module path to discover steps from (optional - if not provided, discovers all modules)",
    )
    get_dsl_parser.add_argument(
        "--base-path",
        default=None,
        help="Base path to discover modules from (only used when --module is not provided, defaults to CLONE_DIR env var or current directory)",
    )
    get_dsl_parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT_FILE,
        help=f"Output file path to write JSON DSL to (default: {DEFAULT_OUTPUT_FILE})",
    )
    get_dsl_parser.set_defaults(func=cmd_config_get_dsl)

    # 'run' command
    run_parser = subparsers.add_parser("run", help="Run a specific step")
    run_parser.add_argument("--step", required=True, help="Name of the step to run")
    run_parser.add_argument(
        "--results", required=True, help='Json of cached results. e.g. {"Step1": "abc"}'
    )
    run_parser.add_argument("--input", required=True, help="Input to the step")
    run_parser.add_argument(
        "--module",
        default="examples",
        help="Module path to discover steps from (default: examples)",
    )
    run_parser.set_defaults(func=cmd_run_step)

    args = parser.parse_args()

    # Check if a command was provided
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    # Execute the command
    args.func(args)


if __name__ == "__main__":
    main()
