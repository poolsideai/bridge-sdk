#!/usr/bin/env python3
"""CLI runner for executing Steps with their setup and post-execution scripts."""

import argparse
import asyncio
import importlib
import sys
import os
from typing import Dict
import json
from pathlib import Path
from lib import STEP_REGISTRY
from lib.step import Step


def load_config_modules() -> list[str]:
    """Load STEP_MODULES from bridge_config.py if it exists."""
    try:
        import bridge_config

        return getattr(bridge_config, "STEP_MODULES", [])
    except ImportError:
        return []


def get_modules_from_args(args) -> list[str]:
    """Combine --module and --modules args, falling back to config file."""
    modules = []
    if args.modules:
        modules.extend(args.modules)
    if not modules:
        modules = load_config_modules()
    return modules


def discover_steps(module_paths: list[str]) -> Dict[str, Step]:
    """Dynamically discover all classes decorated with @step in the specified modules.

    Args:
        module_paths: List of module paths to import and discover steps from.
    """
    for module_path in module_paths:
        try:
            importlib.import_module(module_path)
        except ImportError as e:
            print(f"Error importing module {module_path}: {e}")
            sys.exit(1)
    return STEP_REGISTRY


def cmd_config_get_dsl(args):
    """Handle 'config get-dsl' command."""
    modules = get_modules_from_args(args)
    if not modules:
        print(
            "Error: No modules specified. Use --module, --modules, or configure STEP_MODULES in bridge_config.py"
        )
        sys.exit(1)
    discover_steps(modules)

    # Build DSL dictionary with steps
    dsl_dict = {
        step_name: step.step_data.model_dump()
        for (step_name, step) in STEP_REGISTRY.items()
    }

    # Add commit information if available from environment variables
    commit_hash = os.environ.get("COMMIT_HASH")
    commit_timestamp = os.environ.get("COMMIT_TIMESTAMP")

    if commit_hash or commit_timestamp:
        commit_info = {}
        if commit_hash:
            commit_info["commit_hash"] = commit_hash
        if commit_timestamp:
            # Convert timestamp to integer if it's a string
            try:
                commit_info["commit_timestamp"] = int(commit_timestamp)
            except (ValueError, TypeError):
                commit_info["commit_timestamp"] = commit_timestamp
        dsl_dict["_commit_info"] = commit_info

    dsl_json = json.dumps(dsl_dict, indent=2)

    print(dsl_json)

    # Write to output file
    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(dsl_json)
    print(f"DSL JSON written to {output_path}")


async def cmd_run_step(args):
    """Handle 'run' command to execute a step."""
    # 1. Discover steps from the modules
    modules = get_modules_from_args(args)
    if not modules:
        print(
            "Error: No modules specified. Use --module, --modules, or configure STEP_MODULES in bridge_config.py"
        )
        sys.exit(1)
    steps = discover_steps(modules)
    step_name = args.step

    # 2. Find the step by name
    if step_name not in steps:
        print(steps)
        print(f"Error: Step '{args.step}' not found in modules '{modules}'")
        print(f"Available steps: {', '.join(steps.keys())}")
        sys.exit(1)

    # Parse results JSON
    try:
        cached_results = json.loads(args.results)
    except json.JSONDecodeError as e:
        print(f"Error parsing --results JSON: {e}")
        sys.exit(1)

    # 3. Get the step function
    step = steps[step_name]

    # Verify dependencies are available
    dependencies = step.step_data.depends_on or []
    missing_deps = [dep for dep in dependencies if dep not in cached_results]
    if missing_deps:
        raise ValueError(f"Missing cached results for: {', '.join(missing_deps)}")

    # 5. Call the step function
    try:
        result = await step.on_invoke_step(input=args.input, step_results=args.results)
        print(f"Step '{args.step}' executed successfully")
        print(f"Result: {result}")

        # Write result to output file if specified
        if args.output_file:
            output_path = Path(args.output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # result is already a JSON string from on_invoke_step
            output_path.write_text(result)
            print(f"Result written to {output_path}")
    except Exception as e:
        print(f"Error executing step '{args.step}': {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


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
        "--modules",
        nargs="+",
        help="Module paths to discover steps from (e.g., --modules examples my_steps)",
    )
    get_dsl_parser.add_argument(
        "--output-file",
        default="/tmp/config_get_dsl/dsl.json",
        help="Path to write the DSL JSON file (default: /tmp/config_get_dsl/dsl.json)",
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
        "--modules",
        nargs="+",
        help="Module paths to discover steps from (e.g., --modules examples my_steps)",
    )
    run_parser.add_argument(
        "--output-file",
        help="Path to write the step result to",
    )
    run_parser.add_argument("--output-file", help="Path to write the step result to")
    run_parser.set_defaults(func=cmd_run_step)

    args = parser.parse_args()

    # Check if a command was provided
    if not hasattr(args, "func"):
        parser.print_help()
        sys.exit(1)

    # Execute the command
    if asyncio.iscoroutinefunction(args.func):
        asyncio.run(args.func(args))
    else:
        args.func(args)


if __name__ == "__main__":
    main()
