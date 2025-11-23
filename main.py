#!/usr/bin/env python3
"""CLI runner for executing Steps with their setup and post-execution scripts."""

import argparse
import importlib
import sys
from typing import Any, Dict, get_args
import json
import inspect

from pydantic import BaseModel
from lib import STEP_REGISTRY, StepRecord, STEP_INPUT, extract_step_result_annotation

def load_config_modules() -> list[str]:
    """Load STEP_MODULES from bridge_config.py if it exists."""
    try:
        import bridge_config
        return getattr(bridge_config, 'STEP_MODULES', [])
    except ImportError:
        return []

def get_modules_from_args(args) -> list[str]:
    """Combine --module and --modules args, falling back to config file."""
    modules = []
    if args.module:
        modules.append(args.module)
    if args.modules:
        modules.extend(args.modules)
    if not modules:
        modules = load_config_modules()
    return modules

def discover_steps(module_paths: list[str]) -> Dict[str, StepRecord]:
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
        print("Error: No modules specified. Use --module, --modules, or configure STEP_MODULES in bridge_config.py")
        sys.exit(1)
    discover_steps(modules)
    print({ step: data.data.model_dump_json() for (step, data) in STEP_REGISTRY.items() })


def cmd_run_step(args):
    """Handle 'run' command to execute a step."""
    # 1. Discover steps from the modules
    modules = get_modules_from_args(args)
    if not modules:
        print("Error: No modules specified. Use --module, --modules, or configure STEP_MODULES in bridge_config.py")
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

        # Check if it's an Annotated type
        if (
            param.annotation != inspect.Parameter.empty
            and hasattr(param.annotation, '__metadata__')
            and (metadata := param.annotation.__metadata__)
        ):
            annotation_value = metadata[0]

            # Check if it's a step input
            if annotation_value == STEP_INPUT:
                if type_args := get_args(param.annotation):
                    actual_type = type_args[0]
                    # Check if it's a Pydantic model
                    call_params[param_name] = resolve_step_input(args.input, actual_type)
                else:
                    # No type args, pass as-is
                    call_params[param_name] = args.input

            # Check if it's a step result
            elif step_result_name := extract_step_result_annotation(annotation_value):
                if step_result_name in cached_results:
                    cached_value = cached_results[step_result_name]
                    # Get the actual type from Annotated[Type, metadata]
                    if type_args := get_args(param.annotation):
                        actual_type = type_args[0]
                        # Check if it's a Pydantic model
                        call_params[param_name] = resolve_step_input(cached_value, actual_type)
                    else:
                        # No type args, pass as-is
                        call_params[param_name] = cached_value
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
        description='CLI for discovering and running Steps'
    )
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # 'config get-dsl' command
    config_parser = subparsers.add_parser('config', help='Configuration commands')
    config_subparsers = config_parser.add_subparsers(dest='config_command')

    get_dsl_parser = config_subparsers.add_parser('get-dsl', help='Get DSL for discovered steps')
    get_dsl_parser.add_argument(
        '--module',
        help='Single module path to discover steps from (backwards compatible)'
    )
    get_dsl_parser.add_argument(
        '--modules',
        nargs='+',
        help='Module paths to discover steps from (e.g., --modules examples my_steps)'
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
        help='Single module path to discover steps from (backwards compatible)'
    )
    run_parser.add_argument(
        '--modules',
        nargs='+',
        help='Module paths to discover steps from (e.g., --modules examples my_steps)'
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