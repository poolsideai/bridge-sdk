#!/usr/bin/env python3
"""CLI runner for executing Steps with their setup and post-execution scripts."""

import argparse
import importlib
import sys
import os
from pathlib import Path
from typing import Any, Dict
import json

from pydantic import BaseModel
from lib import STEP_REGISTRY, StepRecord


def discover_steps(module_path: str) -> Dict[str, StepRecord]:
    """Dynamically discover all classes decorated with @step in a module."""
    try:
        # Import the module
        importlib.import_module(module_path)
    except ImportError as e:
        print(f"Error importing module {module_path}: {e}")
        sys.exit(1)
    return STEP_REGISTRY


def cmd_config_get_dsl(args):
    """Handle 'config get-dsl' command."""
    discover_steps(args.module)
    dsl_data = {step: data.data.model_dump() for (step, data) in STEP_REGISTRY.items()}
    print(json.dumps(dsl_data, indent=2))

    # Write DSL to JSON file
    output_file = os.getenv("OUTPUT_FILE", "/tmp/step_result.json")
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(dsl_data, f, indent=2)

    print(f"DSL written to: {output_file}")


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
        "--module", required=True, help="Module path to discover steps from"
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
