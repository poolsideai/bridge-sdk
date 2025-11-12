#!/usr/bin/env python3
"""CLI runner for executing Steps with their setup and post-execution scripts."""

import argparse
import importlib
import sys
from typing import Any, Dict, Type
import json
import inspect

from lib import STEP_REGISTRY, StepData, StepRecord


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

    # 3. Instantiate the step and all dependencies
    instantiated_steps = {}
    step_metadata = steps[step_name].data
    dependencies = step_metadata.depends_on or []
    missing_deps = [dep for dep in dependencies if dep not in cached_results]
    if missing_deps:
        raise ValueError(
            f"Missing cached results for: {', '.join(missing_deps)}"
        )

    for cached_step_name in cached_results:
        cached_step_class = steps[cached_step_name].cls

        # Get constructor signature
        sig = inspect.signature(cached_step_class.__init__)
        init_params = {}

        # Provide None for all parameters
        for param_name, param in sig.parameters.items():
            if param_name == 'self':
                continue
            init_params[param_name] = None  # Provide None for dependencies

        instance = cached_step_class(**init_params)
        instance.set_output(cached_results[cached_step_name])
        instantiated_steps[cached_step_class] = instance

    # 4. Inject dependencies of the step by type
    step_class = steps[step_name].cls
    sig = inspect.signature(step_class.__init__)
    init_params = {}

    for param_name, param in sig.parameters.items():
        if param_name == 'self':
            continue

        # Get the type annotation
        if param.annotation != inspect.Parameter.empty:
            param_type = param.annotation
            # Extract the corresponding instantiated step by type
            init_params[param_name] = instantiated_steps[param_type]

    # Instantiate the step with dependencies
    step_instance = step_class(**init_params)

    # 5. Run the execute method on the step
    try:
        result = step_instance.execute(args.input)
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