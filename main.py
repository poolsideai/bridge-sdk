#!/usr/bin/env python3
"""CLI runner for executing Steps with their setup and post-execution scripts."""

import argparse
import importlib
import sys
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import json

from pydantic import BaseModel
from lib import STEP_REGISTRY, StepRecord, get_dsl_output


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
    print(json.dumps(dsl_output, indent=2))


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

    # 3. Get the step function
    step_func = steps[step_name].func
    step_metadata = steps[step_name].data

    # Verify dependencies are available
    dependencies = step_metadata.depends_on or []
    missing_deps = [dep for dep in dependencies if dep not in cached_results]
    if missing_deps:
        raise ValueError(f"Missing cached results for: {', '.join(missing_deps)}")

    # 4. Build arguments based on pre-extracted parameter information
    call_params = {}
    parameters = step_metadata.parameters or []

    for param_info in parameters:
        param_name = param_info.name

        # Check if it's a step input
        if param_info.is_step_input:
            call_params[param_name] = resolve_step_input(
                args.input, param_info.actual_type
            )

        # Check if it's a step result
        elif param_info.is_step_result:
            step_result_name = param_info.step_result_name
            if step_result_name in cached_results:
                cached_value = cached_results[step_result_name]
                call_params[param_name] = resolve_step_input(
                    cached_value, param_info.actual_type
                )
            else:
                raise ValueError(
                    f"Step result '{step_result_name}' not found in cached results"
                )

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
