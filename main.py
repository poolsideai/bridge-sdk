#!/usr/bin/env python3
"""CLI runner for executing Steps with their setup and post-execution scripts."""

import argparse
import importlib
import sys
from typing import Any, Dict, Type
import json
import inspect

from lib import STEP_REGISTRY, StepRecord, STEP_INPUT, extract_step_result_annotation


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
    steps = discover_steps(args.module)
    print({ step: data.data for (step, data) in STEP_REGISTRY.items() })


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
        raise ValueError(
            f"Missing cached results for: {', '.join(missing_deps)}"
        )

    # 4. Inspect function signature and build arguments based on annotations
    sig = inspect.signature(step_func)
    call_params = {}

    for param_name, param in sig.parameters.items():
        if param_name == 'self':
            continue

        # Get the type annotation
        if param.annotation != inspect.Parameter.empty:
            # Check if it's an Annotated type
            if hasattr(param.annotation, '__metadata__'):
                # Extract the annotation metadata
                metadata = param.annotation.__metadata__
                if metadata:
                    annotation_value = metadata[0]
                    # Check if it's a step input
                    if annotation_value == STEP_INPUT:
                        call_params[param_name] = args.input
                    # Check if it's a step result
                    elif step_result_name := extract_step_result_annotation(annotation_value):
                        if step_result_name in cached_results:
                            call_params[param_name] = cached_results[step_result_name]
                        else:
                            raise ValueError(
                                f"Step result '{step_result_name}' not found in cached results"
                            )

    # 5. Call the step function
    try:
        result = step_func(**call_params)
        print(f"Step '{args.step}' executed successfully")
        print(f"Result: {result}")
    except Exception as e:
        print(f"Error executing step '{args.step}': {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description='CLI for discovering and running Steps'
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # 'config get-dsl' command
    config_parser = subparsers.add_parser('config', help='Configuration commands')
    config_subparsers = config_parser.add_subparsers(dest='config_command')

    get_dsl_parser = config_subparsers.add_parser('get-dsl', help='Get DSL for discovered steps')
    get_dsl_parser.add_argument(
        '--module',
        required=True,
        help='Module path to discover steps from'
    )
    get_dsl_parser.set_defaults(func=cmd_config_get_dsl)

    # 'run' command
    run_parser = subparsers.add_parser('run', help='Run a specific step')
    run_parser.add_argument(
        '--step',
        required=True,
        help='Name of the step to run'
    )
    run_parser.add_argument(
        '--results',
        required=True,
        help='Json of cached results. e.g. {"Step1": "abc"}'
    )
    run_parser.add_argument(
        '--input',
        required=True,
        help='Input to the step'
    )
    run_parser.add_argument(
        '--module',
        default='examples',
        help='Module path to discover steps from (default: examples)'
    )
    run_parser.set_defaults(func=cmd_run_step)

    args = parser.parse_args()

    # Check if a command was provided
    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)

    # Execute the command
    args.func(args)


if __name__ == '__main__':
    main()